"""The LLMProvider contract.

Agents never talk to Ollama or Claude directly. They call a provider with two
methods, so the model can be swapped with one setting.
"""
from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Raised when the LLM cannot give a usable answer after retries."""


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, *, model: str, system: str = "") -> str:
        """Free-text answer."""

    @abstractmethod
    async def generate_structured(self, prompt: str, schema: type[T], *, model: str, system: str = "") -> T:
        """Answer forced into the shape of a Pydantic model, checked before returning."""
