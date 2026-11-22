"""Pick the LLM backend from the MEMOGRAPH_LLM_PROVIDER setting."""
from memograph.core.config import settings
from memograph.core.llm.base import LLMError, LLMProvider


def get_provider() -> LLMProvider:
    if settings.llm_provider == "ollama":
        from memograph.core.llm.ollama import OllamaProvider
        return OllamaProvider(settings.ollama_url)
    raise LLMError(f"Unknown LLM provider: {settings.llm_provider}")


__all__ = ["get_provider", "LLMProvider", "LLMError"]
