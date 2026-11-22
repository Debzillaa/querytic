import json
import math
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.analytics.query_engine import build_and_execute_query
from app.analytics.sql_validator import validate_and_prepare_sql
from app.llm.base import LLMProvider
from app.models.dataset import Dataset
from app.schemas.nl_query import NLQueryResponse


def _build_schema_context(db: Session, dataset: Dataset) -> str:
    """Build a compact schema + 3-row sample summary for LLM grounding."""
    inspector = inspect(db.get_bind())
    columns = inspector.get_columns(dataset.table_name)
    col_lines = [f"- {col['name']} ({col['type']})" for col in columns]

    sample_result = db.execute(text(f'SELECT * FROM "{dataset.table_name}" LIMIT 3'))
    sample_rows = [dict(row._mapping) for row in sample_result.fetchall()]

    return (
        f"Dataset: {dataset.original_filename} ({dataset.row_count} rows)\n"
        f"Columns:\n" + "\n".join(col_lines) + "\n\n"
        f"Sample rows (first 3):\n{json.dumps(sample_rows, default=str)}"
    )


def answer_natural_language_question(
    db: Session,
    dataset: Dataset,
    question: str,
    llm: LLMProvider,
) -> NLQueryResponse:
    """
    Full controlled NL -> Structured Plan -> SQL Execution -> Explanation pipeline.
    """
    schema_context = _build_schema_context(db, dataset)

    # 1. Ask LLM for a structured analytical plan (no raw SQL)
    plan = llm.generate_plan(question=question, schema_context=schema_context)

    # 2. Validate & execute via our safe Step 8 query engine
    generated_sql, columns, rows = build_and_execute_query(
        db=db,
        table_name=dataset.table_name,
        query=plan.query,
    )

    # 3. Generate a grounded explanation from actual results
    explanation = llm.explain_results(
        question=question,
        intent_summary=plan.intent_summary,
        generated_sql=generated_sql,
        rows=rows,
    )

    return NLQueryResponse(
        dataset_id=str(dataset.id),
        question=question,
        intent_summary=plan.intent_summary,
        generated_sql=generated_sql,
        row_count=len(rows),
        columns=columns,
        rows=rows,
        explanation=explanation,
    )

def _sanitize_value(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def answer_question_with_sql(
    db: Session,
    readonly_db: Session,
    dataset: Dataset,
    question: str,
    llm: LLMProvider,
) -> NLQueryResponse:
    """
    Controlled NL -> PostgreSQL SQL -> AST Validation -> Read-Only Execution -> Explanation.
    """
    schema_context = _build_schema_context(db, dataset)

    # 1. Generate raw PostgreSQL SQL via LLM
    plan = llm.generate_sql(
        question=question,
        schema_context=schema_context,
        table_name=dataset.table_name,
    )

    # 2. Parse AST and enforce strict read-only & single-table rules
    safe_sql = validate_and_prepare_sql(
        raw_sql=plan.sql,
        allowed_table=dataset.table_name,
    )

    # 3. Execute ONLY on the least-privilege read-only DB session
    result = readonly_db.execute(text(safe_sql))
    columns = list(result.keys())
    rows = [
        {k: _sanitize_value(v) for k, v in row._mapping.items()}
        for row in result.fetchall()
    ]

    # 4. Generate a grounded explanation from actual results
    explanation = llm.explain_results(
        question=question,
        intent_summary=plan.intent_summary,
        generated_sql=safe_sql,
        rows=rows,
    )

    return NLQueryResponse(
        dataset_id=str(dataset.id),
        question=question,
        intent_summary=plan.intent_summary,
        generated_sql=safe_sql,
        row_count=len(rows),
        columns=columns,
        rows=rows,
        explanation=explanation,
    )