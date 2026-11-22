from typing import Any

from pydantic import BaseModel, Field

from app.schemas.analytics import AnalyticsQueryRequest


class NLQueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)


class AnalyticalPlan(BaseModel):
    intent_summary: str = Field(
        ...,
        description="One-sentence summary of what the query computes to answer the question.",
    )
    query: AnalyticsQueryRequest

class SQLGenerationPlan(BaseModel):
    intent_summary: str = Field(
        ...,
        description="One-sentence summary of what the SQL query computes.",
    )
    sql: str = Field(
        ...,
        description="A single read-only PostgreSQL SELECT query against the target table.",
    )


class NLQueryResponse(BaseModel):
    dataset_id: str
    question: str
    intent_summary: str
    generated_sql: str
    row_count: int
    columns: list[str]
    rows: list[dict[str, Any]]
    explanation: str