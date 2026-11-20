from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.schemas.dataset import DatasetUploadResponse
from app.services.dataset_service import load_csv

router = APIRouter(prefix="/api/datasets", tags=["Datasets"])

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit
CHUNK_SIZE = 1024 * 1024  # Read 1 MB at a time


@router.post(
    "/upload",
    response_model=DatasetUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_dataset(file: UploadFile = File(...)):
    """
    Upload a CSV dataset, validate its format and contents, and return basic metadata.
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .csv files are currently supported.",
        )

    dataset_id = str(uuid4())
    destination = DATA_DIR / f"{dataset_id}.csv"
    total_bytes = 0

    try:
        with destination.open("wb") as buffer:
            while chunk := await file.read(CHUNK_SIZE):
                total_bytes += len(chunk)
                if total_bytes > MAX_FILE_SIZE_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="File exceeds the 10 MB size limit.",
                    )
                buffer.write(chunk)
    except HTTPException:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    if total_bytes == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    try:
        df = load_csv(destination)
    except ValueError as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return DatasetUploadResponse(
        dataset_id=dataset_id,
        original_filename=file.filename,
        size_bytes=total_bytes,
        row_count=len(df),
        column_count=len(df.columns),
        columns=df.columns.tolist(),
        status="uploaded",
    )