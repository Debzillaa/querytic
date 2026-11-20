from pydantic import BaseModel


class DatasetUploadResponse(BaseModel):
    dataset_id: str
    original_filename: str
    size_bytes: int
    row_count: int
    column_count: int
    columns: list[str]
    status: str