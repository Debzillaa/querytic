import math
import re
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.schemas.analytics import AnalyticsQueryRequest

ALIAS_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,54}$")

OPERATOR_SQL = {
    "eq": "=",
    "neq": "!=",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
}


def _quote_ident(name: str) -> str:
    """Safely double-quote an already-validated PostgreSQL identifier."""
    return f'"{name}"'


def _sanitize_value(value: Any) -> Any:
    """Convert non-finite floats (NaN/Inf) to None for valid JSON output."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def get_table_columns(db: Session, table_name: str) -> set[str]:
    """Fetch the actual column names of a PostgreSQL table as an allowlist."""
    inspector = inspect(db.get_bind())
    if not inspector.has_table(table_name):
        raise ValueError(f"Backing table '{table_name}' does not exist.")
    return {col["name"] for col in inspector.get_columns(table_name)}


def _validate_column(column: str, allowed_columns: set[str]) -> None:
    if column not in allowed_columns:
        raise ValueError(
            f"Unknown column '{column}'. Available columns: {sorted(allowed_columns)}"
        )


def build_and_execute_query(
    db: Session,
    table_name: str,
    query: AnalyticsQueryRequest,
) -> tuple[str, list[str], list[dict[str, Any]]]:
    """
    Validate a structured AnalyticsQueryRequest against the table schema,
    compile a parameterized SQL query, execute it, and return (sql, columns, rows).
    """
    allowed_columns = get_table_columns(db, table_name)
    params: dict[str, Any] = {}
    select_parts: list[str] = []
    agg_aliases: set[str] = set()

    # 1. Build SELECT clause
    if query.group_by or query.aggregations:
        for col in query.group_by:
            _validate_column(col, allowed_columns)
            select_parts.append(_quote_ident(col))

        for agg in query.aggregations:
            _validate_column(agg.column, allowed_columns)
            alias = agg.alias or f"{agg.func}_{agg.column}"
            if not ALIAS_PATTERN.match(alias):
                raise ValueError(
                    f"Invalid alias '{alias}'. Use lowercase letters, digits, and underscores."
                )
            agg_aliases.add(alias)
            sql_func = agg.func.upper()
            select_parts.append(
                f"{sql_func}({_quote_ident(agg.column)}) AS {_quote_ident(alias)}"
            )
    elif query.columns:
        for col in query.columns:
            _validate_column(col, allowed_columns)
            select_parts.append(_quote_ident(col))
    else:
        select_parts.append("*")

    sql_clauses = [f"SELECT {', '.join(select_parts)}", f"FROM {_quote_ident(table_name)}"]

    # 2. Build WHERE clause with bound parameters
    if query.filters:
        where_parts: list[str] = []
        for idx, flt in enumerate(query.filters):
            _validate_column(flt.column, allowed_columns)
            param_name = f"p_{idx}"
            col_ident = _quote_ident(flt.column)

            if flt.operator == "contains":
                where_parts.append(f"CAST({col_ident} AS TEXT) ILIKE :{param_name}")
                params[param_name] = f"%{flt.value}%"
            else:
                sql_op = OPERATOR_SQL[flt.operator]
                where_parts.append(f"{col_ident} {sql_op} :{param_name}")
                params[param_name] = flt.value

        sql_clauses.append(f"WHERE {' AND '.join(where_parts)}")

    # 3. Build GROUP BY clause
    if query.group_by:
        group_idents = ", ".join(_quote_ident(c) for c in query.group_by)
        sql_clauses.append(f"GROUP BY {group_idents}")

    # 4. Build ORDER BY clause (allows real columns or aggregation aliases)
    if query.order_by:
        valid_sort_targets = allowed_columns | agg_aliases
        order_parts: list[str] = []
        for sort in query.order_by:
            if sort.column not in valid_sort_targets:
                raise ValueError(f"Cannot sort by unknown column or alias '{sort.column}'.")
            order_parts.append(f"{_quote_ident(sort.column)} {sort.direction.upper()}")
        sql_clauses.append(f"ORDER BY {', '.join(order_parts)}")

    # 5. Build LIMIT clause
    sql_clauses.append("LIMIT :row_limit")
    params["row_limit"] = query.limit

    compiled_sql = "\n".join(sql_clauses)

    # 6. Execute safely
    result = db.execute(text(compiled_sql), params)
    result_columns = list(result.keys())
    rows = [
        {k: _sanitize_value(v) for k, v in row._mapping.items()}
        for row in result.fetchall()
    ]

    return compiled_sql, result_columns, rows