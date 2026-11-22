import math

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.analytics import (
    CorrelationMethod,
    CorrelationPair,
    TimeAgg,
    TimeFreq,
    TimeSeriesPoint,
)

FREQ_MAP: dict[TimeFreq, str] = {
    "D": "D",
    "W": "W",
    "M": "ME",
    "Q": "QE",
    "Y": "YE",
}


def _safe_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    result = float(value)
    if not math.isfinite(result):
        return None
    return round(result, 4)


def load_table_as_dataframe(db: Session, table_name: str) -> pd.DataFrame:
    """Load a dataset's PostgreSQL table into a Pandas DataFrame."""
    query = text(f'SELECT * FROM "{table_name}"')
    return pd.read_sql(query, con=db.connection())


def compute_correlations(
    df: pd.DataFrame,
    method: CorrelationMethod = "pearson",
) -> tuple[list[str], dict[str, dict[str, float | None]], list[CorrelationPair]]:
    """
    Compute the correlation matrix for all numeric columns and return
    (numeric_columns, matrix, top_pairs sorted by absolute strength).
    """
    numeric_df = df.select_dtypes(include="number")
    numeric_cols = numeric_df.columns.tolist()

    if len(numeric_cols) < 2:
        raise ValueError(
            "At least 2 numeric columns are required to compute correlations."
        )

    corr_df = numeric_df.corr(method=method)

    matrix: dict[str, dict[str, float | None]] = {
        row_col: {
            col_name: _safe_float(corr_df.loc[row_col, col_name])
            for col_name in numeric_cols
        }
        for row_col in numeric_cols
    }

    pairs: list[CorrelationPair] = []
    for i, col_a in enumerate(numeric_cols):
        for col_b in numeric_cols[i + 1 :]:
            val = matrix[col_a][col_b]
            if val is not None:
                pairs.append(
                    CorrelationPair(column_a=col_a, column_b=col_b, correlation=val)
                )

    pairs.sort(key=lambda p: abs(p.correlation), reverse=True)
    return numeric_cols, matrix, pairs[:10]


def compute_timeseries(
    df: pd.DataFrame,
    date_column: str,
    value_column: str,
    freq: TimeFreq = "M",
    agg: TimeAgg = "sum",
) -> list[TimeSeriesPoint]:
    """
    Parse a date column, resample a numeric column by the requested frequency,
    and return chronological (period, value) points.
    """
    if date_column not in df.columns:
        raise ValueError(f"Unknown date column '{date_column}'.")
    if value_column not in df.columns:
        raise ValueError(f"Unknown value column '{value_column}'.")

    if not pd.api.types.is_numeric_dtype(df[value_column]):
        raise ValueError(f"Column '{value_column}' must be numeric for aggregation.")

    ts_df = df[[date_column, value_column]].copy()
    ts_df[date_column] = pd.to_datetime(ts_df[date_column], errors="coerce")
    ts_df = ts_df.dropna(subset=[date_column])

    if ts_df.empty:
        raise ValueError(
            f"Column '{date_column}' could not be parsed as valid dates."
        )

    ts_df = ts_df.set_index(date_column).sort_index()
    resampled = getattr(ts_df[value_column].resample(FREQ_MAP[freq]), agg)()

    return [
        TimeSeriesPoint(
            period=idx.strftime("%Y-%m-%d"),
            value=_safe_float(val),
        )
        for idx, val in resampled.items()
    ]