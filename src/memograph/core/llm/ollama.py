"""Ollama backend: runs open-source models on your own Mac."""
import asyncio

import httpx
from pydantic import ValidationError

from memograph.core.llm.base import LLMError, LLMProvider, T

RETRIES = 3          # try a failing network call up to 3 times
TIMEOUT_S = 300      # local 14B models can be slow


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def _chat(self, messages: list[dict], model: str, fmt: dict | None = None) -> str:
        body = {"model": model, "messages": messages, "stream": False, "options": {"temperature": 0}}
        if model.startswith("qwen3"):
            body["think"] = False  # Qwen3 "thinks out loud" by default; off = faster, cleaner JSON
        if fmt is not None:
            body["format"] = fmt  # Ollama forces the reply to match this JSON schema
        last_error: Exception | None = None
        for attempt in range(RETRIES):
            try:
                async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
                    r = await client.post(f"{self.base_url}/api/chat", json=body)
                if r.status_code == 404:
                    raise LLMError(f"Model '{model}' not found. Run: ollama pull {model}")
                r.raise_for_status()
                return r.json()["message"]["content"]
            except LLMError:
                raise
            except Exception as e:  # network hiccup: wait 1s, 2s, 4s and retry
                last_error = e
                await asyncio.sleep(2 ** attempt)
        raise LLMError(f"Ollama failed after {RETRIES} tries: {last_error}")

    async def generate(self, prompt: str, *, model: str, system: str = "") -> str:
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        return await self._chat(messages, model)

    async def generate_structured(self, prompt: str, schema: type[T], *, model: str, system: str = "") -> T:
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        raw = await self._chat(messages, model, fmt=schema.model_json_schema())
        try:
            return schema.model_validate_json(raw)
        except ValidationError as e:
            # One repair pass: show the model its own mistake and ask again.
            messages += [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": f"That JSON was invalid: {e}. Reply again with corrected JSON only."},
            ]
            raw = await self._chat(messages, model, fmt=schema.model_json_schema())
            try:
                return schema.model_validate_json(raw)
            except ValidationError as e2:
                raise LLMError(f"Bad output after repair: {e2}") from e2
