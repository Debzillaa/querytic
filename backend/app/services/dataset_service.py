from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError, ParserError


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