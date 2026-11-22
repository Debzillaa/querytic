from abc import ABC, abstractmethod
from typing import Any

from app.schemas.nl_query import AnalyticalPlan


class LLMProvider(ABC):
    """Provider-agnostic interface for LLM analytical planning and explanation."""

    @abstractmethod
    def generate_plan(self, question: str, schema_context: str) -> AnalyticalPlan:
        """Translate a natural-language question into a structured AnalyticalPlan."""

    @abstractmethod
    def explain_results(
        self,
        question: str,
        intent_summary: str,
        generated_sql: str,
        rows: list[dict[str, Any]],
    ) -> str:
        """Generate a concise, grounded natural-language explanation of query results."""