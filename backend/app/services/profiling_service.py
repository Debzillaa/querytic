import math

import pandas as pd

from app.schemas.dataset import (
    CategoryValue,
    ColumnProfile,
    DatasetProfileResponse,
    NumericStats,
)


def _safe_float(value: object) -> float | None:
    """Convert a NumPy/Pandas scalar to a JSON-safe Python float."""
    if value is None or pd.isna(value):
        return None
    result = float(value)
    if not math.isfinite(result):
        return None
    return round(result, 4)


def _profile_column(series: pd.Series) -> ColumnProfile:
    total_rows = len(series)
    missing_count = int(series.isna().sum())
    missing_pct = round((missing_count / total_rows) * 100, 2) if total_rows > 0 else 0.0
    unique_count = int(series.nunique(dropna=True))

    numeric_stats: NumericStats | None = None
    top_values: list[CategoryValue] | None = None

    # Check boolean before numeric to avoid quantile errors on bool series
    if pd.api.types.is_bool_dtype(series):
        inferred_type = "boolean"
        counts = series.dropna().astype(str).value_counts().head(5)
        top_values = [CategoryValue(value=str(k), count=int(v)) for k, v in counts.items()]
    elif pd.api.types.is_numeric_dtype(series):
        inferred_type = "numeric"
        numeric_stats = NumericStats(
            min=_safe_float(series.min()),
            max=_safe_float(series.max()),
            mean=_safe_float(series.mean()),
            median=_safe_float(series.median()),
            std=_safe_float(series.std()),
            q25=_safe_float(series.quantile(0.25)),
            q75=_safe_float(series.quantile(0.75)),
        )
    elif pd.api.types.is_datetime64_any_dtype(series):
        inferred_type = "datetime"
    else:
        inferred_type = "categorical"
        counts = series.dropna().astype(str).value_counts().head(5)
        top_values = [CategoryValue(value=str(k), count=int(v)) for k, v in counts.items()]

    return ColumnProfile(
        name=str(series.name),
        dtype=str(series.dtype),
        inferred_type=inferred_type,
        missing_count=missing_count,
        missing_percentage=missing_pct,
        unique_count=unique_count,
        numeric_stats=numeric_stats,
        top_values=top_values,
    )


def generate_dataset_profile(df: pd.DataFrame, dataset_id: str) -> DatasetProfileResponse:
    """Compute dataset-level and column-level statistics for a DataFrame."""
    row_count = len(df)
    column_count = len(df.columns)
    total_cells = row_count * column_count

    missing_total = int(df.isna().sum().sum())
    missing_pct = round((missing_total / total_cells) * 100, 2) if total_cells > 0 else 0.0
    duplicate_rows = int(df.duplicated().sum())
    memory_usage = int(df.memory_usage(deep=True).sum())

    column_profiles = [_profile_column(df[col]) for col in df.columns]

    return DatasetProfileResponse(
        dataset_id=dataset_id,
        row_count=row_count,
        column_count=column_count,
        missing_values_total=missing_total,
        missing_percentage=missing_pct,
        duplicate_rows=duplicate_rows,
        memory_usage_bytes=memory_usage,
        columns=column_profiles,
    )