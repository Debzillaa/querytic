import json
from typing import Any

from google import genai
from google.genai import types

from app.llm.base import LLMProvider
from app.schemas.nl_query import AnalyticalPlan


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gemini-3.8-flash") -> None:
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def generate_plan(self, question: str, schema_context: str) -> AnalyticalPlan:
        prompt = (
            "You are a senior data analyst translating a user's question into a "
            "structured analytical query.\n"
            "Rules:\n"
            "- ONLY use exact column names from the schema below.\n"
            "- If you aggregate a column, give it a clean snake_case alias.\n"
            "- Keep limit reasonable (default 20 unless the user asks for top N).\n"
            "- Never invent columns that are not in the schema.\n\n"
            f"DATASET SCHEMA:\n{schema_context}\n\n"
            f"USER QUESTION:\n{question}"
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AnalyticalPlan,
                temperature=0.0,
            ),
        )

        if not response.text:
            raise ValueError("LLM returned an empty analytical plan.")

        return AnalyticalPlan.model_validate_json(response.text)

    def explain_results(
        self,
        question: str,
        intent_summary: str,
        generated_sql: str,
        rows: list[dict[str, Any]],
    ) -> str:
        # Cap rows sent back to the LLM to control token usage
        preview_rows = rows[:20]
        prompt = (
            "You are a data analyst explaining query results to a user.\n"
            "Rules:\n"
            "- Answer the user's question directly using ONLY the provided rows.\n"
            "- Never fabricate numbers or extrapolate beyond the data.\n"
            "- Be concise (2-4 sentences).\n\n"
            f"USER QUESTION: {question}\n"
            f"ANALYTICAL PLAN: {intent_summary}\n"
            f"EXECUTED SQL:\n{generated_sql}\n\n"
            f"TOTAL ROWS RETURNED: {len(rows)}\n"
            f"RESULT PREVIEW (up to 20 rows):\n{json.dumps(preview_rows, default=str)}"
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.2),
        )

        return (response.text or "Unable to generate an explanation.").strip()