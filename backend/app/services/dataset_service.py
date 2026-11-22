import re
from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError, ParserError
from sqlalchemy.orm import Session


def load_csv(file_path: Path) -> pd.DataFrame:
    """
    Load and validate a CSV file into a Pandas DataFrame.
    Raises ValueError with a user-friendly message if the file is malformed.
    """
    try:
        df = pd.read_csv(file_path)
    except EmptyDataError as exc:
        raise ValueError("The CSV file contains no parseable data or headers.") from exc
    except ParserError as exc:
        raise ValueError(f"Malformed CSV structure: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise ValueError("File is not valid UTF-8 text. Please upload a UTF-8 encoded CSV.") from exc

    if df.empty or len(df.columns) == 0:
        raise ValueError("The CSV file contains headers but no data rows.")

    return df


def sanitize_column_names(columns: list[str]) -> list[str]:
    """
    Normalize CSV headers into clean, unique, SQL-safe PostgreSQL column names.
    Example: 'Total Revenue ($)' -> 'total_revenue', '1st_qtr' -> 'col_1st_qtr'
    """
    sanitized: list[str] = []
    seen: dict[str, int] = {}

    for raw_col in columns:
        name = str(raw_col).strip().lower()
        name = re.sub(r"[^a-z0-9]+", "_", name).strip("_")

        if not name:
            name = "col"
        if name[0].isdigit():
            name = f"col_{name}"

        # PostgreSQL max identifier length is 63 bytes
        name = name[:55]

        if name in seen:
            seen[name] += 1
            unique_name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
            unique_name = name

        sanitized.append(unique_name)

    return sanitized


def save_dataframe_to_postgres(
    df: pd.DataFrame,
    table_name: str,
    db: Session,
) -> None:
    """
    Write a DataFrame into a dedicated PostgreSQL table using the active DB transaction.
    """
    df.to_sql(
        name=table_name,
        con=db.connection(),
        if_exists="fail",
        index=False,
        method="multi",
        chunksize=1000,
    )