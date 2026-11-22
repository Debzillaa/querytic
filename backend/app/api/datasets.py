from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.dataset import Dataset
from app.schemas.dataset import (
    DatasetProfileResponse,
    DatasetSummary,
    DatasetUploadResponse,
)
from app.services.dataset_service import (
    load_csv,
    sanitize_column_names,
    save_dataframe_to_postgres,
)
from app.services.profiling_service import generate_dataset_profile

router = APIRouter(prefix="/api/datasets", tags=["Datasets"])

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit
CHUNK_SIZE = 1024 * 1024  # Read 1 MB at a time


@router.get(
    "",
    response_model=list[DatasetSummary],
    status_code=status.HTTP_200_OK,
)
def list_datasets(db: Session = Depends(get_db)):
    """
    Return all uploaded datasets ordered by most recent first.
    """
    stmt = select(Dataset).order_by(Dataset.created_at.desc())
    return db.scalars(stmt).all()


@router.post(
    "/upload",
    response_model=DatasetUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_dataset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a CSV dataset, validate it, persist rows + metadata in PostgreSQL,
    and return basic metadata.
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .csv files are currently supported.",
        )

    dataset_uuid = uuid4()
    dataset_id = str(dataset_uuid)
    table_name = f"ds_{dataset_uuid.hex}"
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
        df.columns = sanitize_column_names(df.columns.tolist())
    except ValueError as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    try:
        save_dataframe_to_postgres(df, table_name, db)
        dataset_record = Dataset(
            id=dataset_uuid,
            original_filename=file.filename,
            table_name=table_name,
            size_bytes=total_bytes,
            row_count=len(df),
            column_count=len(df.columns),
        )
        db.add(dataset_record)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store dataset in database.",
        ) from exc

    return DatasetUploadResponse(
        dataset_id=dataset_id,
        original_filename=file.filename,
        table_name=table_name,
        size_bytes=total_bytes,
        row_count=len(df),
        column_count=len(df.columns),
        columns=df.columns.tolist(),
        status="uploaded",
    )


@router.get(
    "/{dataset_id}/profile",
    response_model=DatasetProfileResponse,
    status_code=status.HTTP_200_OK,
)
def get_dataset_profile(dataset_id: UUID):
    """
    Generate and return a statistical profile for an uploaded dataset.
    """
    file_path = DATA_DIR / f"{dataset_id}.csv"
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found.",
        )

    try:
        df = load_csv(file_path)
        df.columns = sanitize_column_names(df.columns.tolist())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return generate_dataset_profile(df, str(dataset_id))