from pydantic import BaseModel


class DatasetUploadResponse(BaseModel):
    dataset_id: str
    original_filename: str
    size_bytes: int
    row_count: int
    column_count: int
    columns: list[str]
    status: str


class NumericStats(BaseModel):
    min: float | None = None
    max: float | None = None
    mean: float | None = None
    median: float | None = None
    std: float | None = None
    q25: float | None = None
    q75: float | None = None


class CategoryValue(BaseModel):
    value: str
    count: int


class ColumnProfile(BaseModel):
    name: str
    dtype: str
    inferred_type: str  # "numeric", "categorical", "boolean", "datetime"
    missing_count: int
    missing_percentage: float
    unique_count: int
    numeric_stats: NumericStats | None = None
    top_values: list[CategoryValue] | None = None


class DatasetProfileResponse(BaseModel):
    dataset_id: str
    row_count: int
    column_count: int
    missing_values_total: int
    missing_percentage: float
    duplicate_rows: int
    memory_usage_bytes: int
    columns: list[ColumnProfile]