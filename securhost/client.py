"""
The SecurHost Python client.
"""

from __future__ import annotations

import json
import os
import random
import time
from collections.abc import Iterator
from typing import Any

import httpx

from securhost.errors import (
    SecurHostAPIError,
    SecurHostAuthError,
    SecurHostConnectionError,
    SecurHostRateLimitError,
)
from securhost.types import ChatResponse, Cost, EmbeddingResponse, Usage

DEFAULT_BASE_URL = "https://api.securhost.com"
FALLBACK_BASE_URL = "https://securhost.com"
DEFAULT_TIMEOUT = 60.0
DEFAULT_MAX_RETRIES = 3


def _normalize_base_url(url: str | None) -> str:
    if not url:
        return os.environ.get("SECURHOST_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    u = url.rstrip("/")
    return u


class _Chat:
    def __init__(self, client: SecurHostClient) -> None:
        self._client = client

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str = "gpt-4o",
        request_type: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        response_format: dict[str, Any] | None = None,
        user: str | None = None,
        no_cache: bool = False,
        budget_limit_usd: float | None = None,
        **extra: Any,
    ) -> ChatResponse:
        """Execute a smart-routed chat completion with cost telemetry."""
        payload: dict[str, Any] = {"model": model, "messages": messages, **extra}

        if request_type is not None:
            payload["securhost_request_type"] = request_type
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature
        if top_p is not None:
            payload["top_p"] = top_p
        if frequency_penalty is not None:
            payload["frequency_penalty"] = frequency_penalty
        if presence_penalty is not None:
            payload["presence_penalty"] = presence_penalty
        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if response_format is not None:
            payload["response_format"] = response_format
        if user is not None:
            payload["user"] = user
        if no_cache:
            payload["securhost_no_cache"] = True
        if budget_limit_usd is not None:
            payload["securhost_budget_limit_usd"] = budget_limit_usd

        response = self._client._post("/v1/chat/completions", payload)
        body = response.json()

        return ChatResponse(
            raw=body,
            usage=Usage.from_envelope(body),
            cost=Cost.from_headers(response.headers),
            request_id=response.headers.get("X-SecurHost-Request-Id", ""),
        )

    def stream(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str = "gpt-4o",
        request_type: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **extra: Any,
    ) -> Iterator[str]:
        """Yield streaming content token deltas."""
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            **extra,
        }
        if request_type is not None:
            payload["securhost_request_type"] = request_type
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        with self._client._stream("/v1/chat/completions", payload) as response:
            for line in response.iter_lines():
                if not line or not line.startswith("data:"):
                    continue

                data = line[5:].strip()
                if data == "[DONE]":
                    return

                try:
                    event = json.loads(data)
                except ValueError:
                    continue

                try:
                    delta = event["choices"][0]["delta"].get("content")
                except (KeyError, IndexError, TypeError):
                    continue

                if delta:
                    yield delta


class _Voice:
    """Voice AI sessions, speech synthesis, and outbound calling."""
    def __init__(self, client: SecurHostClient) -> None:
        self._client = client

    def create_session(
        self,
        *,
        persona_id: int | None = None,
        voice_id: str = "alloy",
        system_prompt: str | None = None,
        model: str = "gpt-4o-realtime",
        **settings: Any,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "voice": voice_id,
            "model": model,
            **settings,
        }
        if persona_id is not None:
            payload["persona_id"] = persona_id
        if system_prompt is not None:
            payload["system_prompt"] = system_prompt
        return self._client._post("/v1/voice/sessions", payload).json()

    def initiate_call(
        self,
        *,
        to_number: str,
        persona_id: int | None = None,
        prompt: str | None = None,
        callback_url: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"to": to_number}
        if persona_id is not None:
            payload["persona_id"] = persona_id
        if prompt is not None:
            payload["prompt"] = prompt
        if callback_url is not None:
            payload["callback_url"] = callback_url
        return self._client._post("/v1/voice/calls", payload).json()

    def call_logs(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return self._client._get(f"/v1/voice/calls?limit={limit}").json().get("data", [])


class _JobAgents:
    """Autonomous job agents management."""
    def __init__(self, client: SecurHostClient) -> None:
        self._client = client

    def create(
        self,
        *,
        name: str,
        role_brief: dict[str, Any] | None = None,
        autonomy_level: int = 0,
        daily_action_cap: int = 50,
        sandbox: bool = True,
        tools: list[str] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": name,
            "role_brief": role_brief or {},
            "autonomy_level": autonomy_level,
            "daily_action_cap": daily_action_cap,
            "sandbox": sandbox,
        }
        if tools is not None:
            payload["tools"] = tools
        return self._client._post("/v1/job-agents", payload).json()

    def list(self) -> list[dict[str, Any]]:
        return self._client._get("/v1/job-agents").json().get("data", [])

    def get(self, agent_id: int) -> dict[str, Any]:
        return self._client._get(f"/v1/job-agents/{agent_id}").json()

    def pause(self, agent_id: int, *, reason: str | None = None) -> dict[str, Any]:
        payload = {"reason": reason} if reason else {}
        return self._client._post(f"/v1/job-agents/{agent_id}/pause", payload).json()

    def resume(self, agent_id: int) -> dict[str, Any]:
        return self._client._post(f"/v1/job-agents/{agent_id}/resume", {}).json()

    def activity(self, agent_id: int, *, limit: int = 50) -> list[dict[str, Any]]:
        return self._client._get(f"/v1/job-agents/{agent_id}/activity?limit={limit}").json().get("data", [])


class _Personas:
    """Custom personas and prompt templates."""
    def __init__(self, client: SecurHostClient) -> None:
        self._client = client

    def list(self) -> list[dict[str, Any]]:
        return self._client._get("/v1/personas").json().get("data", [])

    def create(
        self,
        *,
        name: str,
        system_prompt: str,
        default_model: str = "gpt-4o",
        tools: list[str] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "name": name,
            "system_prompt": system_prompt,
            "default_model": default_model,
            "tools": tools or [],
        }
        return self._client._post("/v1/personas", payload).json()


class _Chatbots:
    """Website embed chatbots."""
    def __init__(self, client: SecurHostClient) -> None:
        self._client = client

    def list(self) -> list[dict[str, Any]]:
        return self._client._get("/v1/chatbots").json().get("data", [])

    def create(
        self,
        *,
        name: str,
        allowed_domains: list[str] | None = None,
        greeting: str = "Hello! How can I help you today?",
        persona_id: int | None = None,
    ) -> dict[str, Any]:
        payload = {
            "name": name,
            "allowed_domains": allowed_domains or ["*"],
            "greeting": greeting,
        }
        if persona_id is not None:
            payload["persona_id"] = persona_id
        return self._client._post("/v1/chatbots", payload).json()


class _Connectors:
    """Enterprise connectors (Odoo, ServiceNow, SAP, Dynamics 365, Slack, MCP)."""
    def __init__(self, client: SecurHostClient) -> None:
        self._client = client

    def list(self) -> list[dict[str, Any]]:
        return self._client._get("/v1/connectors").json().get("data", [])

    def invoke_tool(
        self,
        connector_id: str,
        *,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {"tool": tool_name, "arguments": arguments or {}}
        return self._client._post(f"/v1/connectors/{connector_id}/invoke", payload).json()


class _Embeddings:
    def __init__(self, client: SecurHostClient) -> None:
        self._client = client

    def create(
        self, texts: list[str] | str, *, model: str = "text-embedding-3-small"
    ) -> EmbeddingResponse:
        response = self._client._post(
            "/v1/embeddings", {"model": model, "input": texts}
        )
        body = response.json()

        return EmbeddingResponse(
            raw=body,
            usage=Usage.from_envelope(body),
            cost=Cost.from_headers(response.headers),
            request_id=response.headers.get("X-SecurHost-Request-Id", ""),
        )


class _Models:
    def __init__(self, client: SecurHostClient) -> None:
        self._client = client

    def list(self) -> list[dict[str, Any]]:
        return self._client._get("/v1/models").json().get("data", [])


class _Usage:
    def __init__(self, client: SecurHostClient) -> None:
        self._client = client

    def summary(self) -> dict[str, Any]:
        return self._client._get("/v1/usage").json()

    def daily(self) -> dict[str, Any]:
        return self._client._get("/v1/usage/daily").json()

    def savings(self) -> dict[str, Any]:
        return self._client._get("/v1/usage/savings").json()


class _Wallet:
    def __init__(self, client: SecurHostClient) -> None:
        self._client = client

    def balance(self) -> dict[str, Any]:
        return self._client._get("/v1/billing/wallet").json()

    def top_up(self, amount: str, *, callback_url: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"amount": str(amount)}
        if callback_url:
            payload["callback_url"] = callback_url
        return self._client._post("/v1/billing/topup", payload).json()

    def invoices(self) -> list[dict[str, Any]]:
        return self._client._get("/v1/billing/invoices").json().get("data", [])


class SecurHostClient:
    """The unified SecurHost client."""
    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: httpx.Client | None = None,
    ) -> None:
        key = api_key or os.environ.get("SECURHOST_API_KEY")
        if not key:
            raise ValueError("An API key is required. Pass api_key or set SECURHOST_API_KEY env var.")

        self.api_key = key
        self.base_url = _normalize_base_url(base_url)
        self.max_retries = max_retries
        self._http = http_client or httpx.Client(timeout=timeout)

        self.chat = _Chat(self)
        self.voice = _Voice(self)
        self.job_agents = _JobAgents(self)
        self.personas = _Personas(self)
        self.chatbots = _Chatbots(self)
        self.connectors = _Connectors(self)
        self.embeddings = _Embeddings(self)
        self.models = _Models(self)
        self.usage = _Usage(self)
        self.wallet = _Wallet(self)

    def __enter__(self) -> SecurHostClient:
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def _headers(self) -> dict[str, str]:
        from securhost import __version__
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"securhost-ai-python/{__version__}",
        }

    def _post(self, path: str, payload: dict[str, Any]) -> httpx.Response:
        return self._request("POST", path, json=payload)

    def _get(self, path: str) -> httpx.Response:
        return self._request("GET", path)

    def _stream(self, path: str, payload: dict[str, Any]):
        return self._http.stream(
            "POST", f"{self.base_url}{path}", json=payload, headers=self._headers()
        )

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = f"{self.base_url}{path}"
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self._http.request(
                    method, url, headers=self._headers(), **kwargs
                )
            except httpx.HTTPError as exc:
                last_error = SecurHostConnectionError(f"Could not reach {url}: {exc}")
                if attempt < self.max_retries:
                    time.sleep(self._backoff(attempt))
                    continue
                raise last_error from exc

            if response.status_code < 400:
                return response

            error = self._as_error(response)

            if error.retryable and attempt < self.max_retries:
                wait = getattr(error, "retry_after", None) or self._backoff(attempt)
                time.sleep(wait)
                last_error = error
                continue

            raise error

        raise last_error or SecurHostConnectionError("Request failed with no response")

    @staticmethod
    def _backoff(attempt: int) -> float:
        return min(2**attempt, 8) * (0.5 + random.random() / 2)

    @staticmethod
    def _as_error(response: httpx.Response) -> SecurHostAPIError:
        status = response.status_code
        body = None
        code = None
        error_type = None
        try:
            body = response.json()
            if isinstance(body, dict):
                err_dict = body.get("error") if isinstance(body.get("error"), dict) else body
                message = err_dict.get("message") or response.text
                code = err_dict.get("code")
                error_type = err_dict.get("type")
            else:
                message = response.text
        except Exception:
            message = response.text

        request_id = response.headers.get("X-SecurHost-Request-Id", "")

        if status in (401, 403):
            return SecurHostAuthError(
                message,
                status_code=status,
                code=code,
                error_type=error_type,
                request_id=request_id,
                body=body,
            )
        if status == 429:
            retry_after = None
            h = response.headers.get("Retry-After")
            if h and h.isdigit():
                retry_after = int(h)
            return SecurHostRateLimitError(
                message,
                status_code=status,
                code=code,
                error_type=error_type,
                request_id=request_id,
                body=body,
                retry_after=retry_after,
            )
        return SecurHostAPIError(
            message,
            status_code=status,
            code=code,
            error_type=error_type,
            request_id=request_id,
            body=body,
        )
