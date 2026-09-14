from __future__ import annotations

import os
import json
from typing import Any

import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
DEFAULT_TIMEOUT_SECONDS = 30.0


class OpenRouterError(RuntimeError):
    """A safe, user-facing OpenRouter failure without secret response data."""

    def __init__(self, message: str, *, provider_status: int | None = None) -> None:
        super().__init__(message)
        self.provider_status = provider_status


class OpenRouterClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("OPENROUTER_API_KEY")
        self.model = model or os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)
        self.timeout = timeout
        self.transport = transport

    def complete(self, prompt: str) -> str:
        if not self.api_key:
            raise OpenRouterError("AI is not configured. Set OPENROUTER_API_KEY on the backend.")

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "reasoning": {"enabled": False},
            "max_tokens": 100,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "Project Management MVP",
        }

        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
                response = client.post(OPENROUTER_URL, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as error:
            raise OpenRouterError("The AI provider timed out. Try again shortly.") from error
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 429:
                message = "The AI provider is rate-limited. Try again shortly."
            else:
                message = "The AI provider returned an error. Try again shortly."
            raise OpenRouterError(message) from error
        except httpx.RequestError as error:
            raise OpenRouterError("The AI provider could not be reached. Try again shortly.") from error

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise OpenRouterError("The AI provider returned an invalid response.") from error

        if not isinstance(content, str) or not content.strip():
            raise OpenRouterError("The AI provider returned an empty response.")
        return content.strip()

    def complete_structured(self, messages: list[dict[str, str]], schema: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise OpenRouterError("AI is not configured. Set OPENROUTER_API_KEY on the backend.")

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "reasoning": {"enabled": False},
            "max_tokens": 1200,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "project_management_response",
                    "strict": True,
                    "schema": schema,
                },
            },
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "Project Management MVP",
        }

        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
                response = client.post(OPENROUTER_URL, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as error:
            raise OpenRouterError("The AI provider timed out. Try again shortly.") from error
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 429:
                message = "The AI provider is rate-limited. Try again shortly."
                raise OpenRouterError(message, provider_status=error.response.status_code) from error
            else:
                return self._complete_structured_without_response_format(messages, schema)
        except httpx.RequestError as error:
            raise OpenRouterError("The AI provider could not be reached. Try again shortly.") from error

        try:
            content = response.json()["choices"][0]["message"]["content"]
            if isinstance(content, dict):
                return content
            if not isinstance(content, str):
                raise ValueError("Structured content was not text or an object")
            return self._parse_json_object(content)
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise OpenRouterError("The AI provider returned invalid structured output.") from error

    def _complete_structured_without_response_format(
        self, messages: list[dict[str, str]], schema: dict[str, Any]
    ) -> dict[str, Any]:
        schema_text = json.dumps(schema, separators=(",", ":"))
        fallback_messages = [
            *messages,
            {
                "role": "system",
                "content": (
                    "Return only one valid JSON object. Do not use markdown fences or explanations. "
                    f"The JSON schema is: {schema_text}"
                ),
            },
        ]
        payload = {
            "model": self.model,
            "messages": fallback_messages,
            "temperature": 0,
            "reasoning": {"enabled": False},
            "max_tokens": 1200,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "Project Management MVP",
        }
        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
                response = client.post(OPENROUTER_URL, headers=headers, json=payload)
                response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            if isinstance(content, dict):
                return content
            if not isinstance(content, str):
                raise ValueError("Fallback structured content was not text or an object")
            return self._parse_json_object(content)
        except httpx.TimeoutException as error:
            raise OpenRouterError("The AI provider timed out. Try again shortly.") from error
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 429:
                message = "The AI provider is rate-limited. Try again shortly."
            else:
                message = "The AI provider returned an error. Try again shortly."
            raise OpenRouterError(message, provider_status=error.response.status_code) from error
        except (httpx.RequestError, ValueError, KeyError, IndexError, TypeError) as error:
            raise OpenRouterError("The AI provider returned invalid structured output.") from error

    @staticmethod
    def _parse_json_object(content: str) -> dict[str, Any]:
        candidate = content.strip()
        if candidate.startswith("```"):
            candidate = candidate.removeprefix("```").removeprefix("json").removesuffix("```").strip()
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start < 0 or end <= start:
                raise
            parsed = json.loads(candidate[start : end + 1])
        if not isinstance(parsed, dict):
            raise ValueError("Structured output root was not an object")
        return parsed

    def connectivity_check(self) -> dict[str, Any]:
        answer = self.complete("What is 2 + 2? Reply with only the number.")
        return {"model": self.model, "answer": answer}
