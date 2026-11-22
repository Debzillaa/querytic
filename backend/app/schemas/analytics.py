from typing import Any, Literal

from pydantic import BaseModel, Field

FilterOperator = Literal["eq", "neq", "gt", "gte", "lt", "lte", "contains"]
AggFunction = Literal["sum", "avg", "count", "min", "max"]
SortDirection = Literal["asc", "desc"]


class FilterCondition(BaseModel):
    column: str
    operator: FilterOperator
    value: str | int | float | bool


class AggregationSpec(BaseModel):
    column: str
    func: AggFunction
    alias: str | None = None


class SortSpec(BaseModel):
    column: str
    direction: SortDirection = "asc"


class AnalyticsQueryRequest(BaseModel):
    columns: list[str] | None = None
    filters: list[FilterCondition] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    aggregations: list[AggregationSpec] = Field(default_factory=list)
    order_by: list[SortSpec] = Field(default_factory=list)
    limit: int = Field(default=100, ge=1, le=1000)


class AnalyticsQueryResponse(BaseModel):
    dataset_id: str
    generated_sql: str
    row_count: int
    columns: list[str]
    rows: list[dict[str, Any]]