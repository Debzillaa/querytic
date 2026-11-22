from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.analytics.query_engine import build_and_execute_query
from app.analytics.stats_engine import (
    compute_correlations,
    compute_timeseries,
    load_table_as_dataframe,
)
from app.core.database import get_db
from app.models.dataset import Dataset
from app.schemas.analytics import (
    AnalyticsQueryRequest,
    AnalyticsQueryResponse,
    CorrelationMethod,
    CorrelationResponse,
    TimeSeriesRequest,
    TimeSeriesResponse,
)

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

@router.get(
    "/{dataset_id}/correlations",
    response_model=CorrelationResponse,
    status_code=status.HTTP_200_OK,
)
def get_dataset_correlations(
    dataset_id: UUID,
    method: CorrelationMethod = Query(default="pearson"),
    db: Session = Depends(get_db),
):
    """
    Compute a correlation matrix and top correlated pairs across numeric columns.
    """
    dataset = db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found.",
        )

    try:
        df = load_table_as_dataframe(db, dataset.table_name)
        numeric_cols, matrix, top_pairs = compute_correlations(df, method=method)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return CorrelationResponse(
        dataset_id=str(dataset_id),
        method=method,
        numeric_columns=numeric_cols,
        matrix=matrix,
        top_pairs=top_pairs,
    )


@router.post(
    "/{dataset_id}/timeseries",
    response_model=TimeSeriesResponse,
    status_code=status.HTTP_200_OK,
)
def get_dataset_timeseries(
    dataset_id: UUID,
    request: TimeSeriesRequest,
    db: Session = Depends(get_db),
):
    """
    Resample a numeric column over a date column at the requested frequency.
    """
    dataset = db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found.",
        )

    try:
        df = load_table_as_dataframe(db, dataset.table_name)
        points = compute_timeseries(
            df=df,
            date_column=request.date_column,
            value_column=request.value_column,
            freq=request.freq,
            agg=request.agg,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return TimeSeriesResponse(
        dataset_id=str(dataset_id),
        date_column=request.date_column,
        value_column=request.value_column,
        freq=request.freq,
        agg=request.agg,
        points=points,
    )