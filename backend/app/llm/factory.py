from app.core.config import settings
from app.llm.base import LLMProvider
from app.llm.gemini_provider import GeminiProvider


def get_llm_provider() -> LLMProvider:
    """Instantiate the configured LLM provider from environment settings."""
    provider_name = settings.llm_provider.lower()

    if provider_name == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not configured in .env.")
        return GeminiProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
        )

    raise ValueError(f"Unsupported LLM provider: '{settings.llm_provider}'.")