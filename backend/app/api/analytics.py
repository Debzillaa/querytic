from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.analytics.query_engine import build_and_execute_query
from app.core.database import get_db
from app.models.dataset import Dataset
from app.schemas.analytics import AnalyticsQueryRequest, AnalyticsQueryResponse

router = APIRouter(prefix="/api/datasets", tags=["Analytics"])


@router.post(
    "/{dataset_id}/query",
    response_model=AnalyticsQueryResponse,
    status_code=status.HTTP_200_OK,
)
def query_dataset(
    dataset_id: UUID,
    query: AnalyticsQueryRequest,
    db: Session = Depends(get_db),
):
    """
    Execute a structured analytical query (filter, group, aggregate, sort)
    against an uploaded dataset's PostgreSQL table.
    """
    dataset = db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found.",
        )

    try:
        generated_sql, columns, rows = build_and_execute_query(
            db=db,
            table_name=dataset.table_name,
            query=query,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Query execution failed: {exc.__class__.__name__}",
        ) from exc

    return AnalyticsQueryResponse(
        dataset_id=str(dataset_id),
        generated_sql=generated_sql,
        row_count=len(rows),
        columns=columns,
        rows=rows,
    )