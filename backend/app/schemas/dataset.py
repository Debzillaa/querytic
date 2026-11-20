from pydantic import BaseModel


class DatasetUploadResponse(BaseModel):
    dataset_id: str
    original_filename: str
    size_bytes: int
    status: str