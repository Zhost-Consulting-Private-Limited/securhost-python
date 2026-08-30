"""Async client. Same surface as SecurHostClient, awaited."""

from __future__ import annotations

import asyncio
import json
import random
from collections.abc import AsyncIterator
from typing import Any

import httpx

from securhost.client import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    SecurHostClient,
)
from securhost.errors import SecurHostConnectionError
from securhost.types import ChatResponse, Cost, EmbeddingResponse, Usage


class _AsyncChat:
    def __init__(self, client: AsyncSecurHostClient) -> None:
        self._client = client

    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str = "gpt-4o",
        request_type: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: list[dict[str, Any]] | None = None,
        no_cache: bool = False,
        **extra: Any,
    ) -> ChatResponse:
        payload: dict[str, Any] = {"model": model, "messages": messages, **extra}

        if request_type is not None:
            payload["securhost_request_type"] = request_type
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature
        if tools is not None:
            payload["tools"] = tools
        if no_cache:
            payload["securhost_no_cache"] = True

        response = await self._client._request("POST", "/v1/chat/completions", json=payload)
        body = response.json()

        return ChatResponse(
            raw=body,
            usage=Usage.from_envelope(body),
            cost=Cost.from_headers(response.headers),
            request_id=response.headers.get("X-SecurHost-Request-Id", ""),
        )

    async def stream(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str = "gpt-4o",
        request_type: str | None = None,
        **extra: Any,
    ) -> AsyncIterator[str]:
        """Yield content deltas. Not retried: tokens already delivered would
        be repeated."""
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            **extra,
        }
        if request_type is not None:
            payload["securhost_request_type"] = request_type

        async with self._client._http.stream(
            "POST",
            f"{self._client.base_url}/v1/chat/completions",
            json=payload,
            headers=self._client._headers(),
        ) as response:
            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue

                data = line[5:].strip()
                if data == "[DONE]":
                    return

                try:
                    event = json.loads(data)
                    delta = event["choices"][0]["delta"].get("content")
                except (ValueError, KeyError, IndexError, TypeError):
                    continue

                if delta:
                    yield delta


class _AsyncEmbeddings:
    def __init__(self, client: AsyncSecurHostClient) -> None:
        self._client = client

    async def create(
        self, texts: list[str] | str, *, model: str = "text-embedding-3-small"
    ) -> EmbeddingResponse:
        response = await self._client._request(
            "POST", "/v1/embeddings", json={"model": model, "input": texts}
        )
        body = response.json()

        return EmbeddingResponse(
            raw=body,
            usage=Usage.from_envelope(body),
            cost=Cost.from_headers(response.headers),
            request_id=response.headers.get("X-SecurHost-Request-Id", ""),
        )


class _AsyncJobAgents:
    def __init__(self, client: AsyncSecurHostClient) -> None:
        self._client = client

    async def create(
        self,
        *,
        name: str,
        role_brief: dict[str, Any] | None = None,
        autonomy_level: int = 0,
        daily_action_cap: int = 50,
    ) -> dict[str, Any]:
        response = await self._client._request(
            "POST",
            "/v1/job-agents",
            json={
                "name": name,
                "role_brief": role_brief or {},
                "autonomy_level": autonomy_level,
                "daily_action_cap": daily_action_cap,
            },
        )
        return response.json()

    async def list(self) -> list[dict[str, Any]]:
        response = await self._client._request("GET", "/v1/job-agents")
        return response.json().get("data", [])

    async def get(self, agent_id: int) -> dict[str, Any]:
        return (await self._client._request("GET", f"/v1/job-agents/{agent_id}")).json()

    async def pause(self, agent_id: int, *, reason: str | None = None) -> dict[str, Any]:
        payload = {"reason": reason} if reason else {}
        response = await self._client._request(
            "POST", f"/v1/job-agents/{agent_id}/pause", json=payload
        )
        return response.json()

    async def resume(self, agent_id: int) -> dict[str, Any]:
        response = await self._client._request(
            "POST", f"/v1/job-agents/{agent_id}/resume", json={}
        )
        return response.json()

    async def activity(self, agent_id: int, *, limit: int = 50) -> list[dict[str, Any]]:
        response = await self._client._request(
            "GET", f"/v1/job-agents/{agent_id}/activity?limit={limit}"
        )
        return response.json().get("data", [])


class _AsyncUsage:
    def __init__(self, client: AsyncSecurHostClient) -> None:
        self._client = client

    async def summary(self) -> dict[str, Any]:
        return (await self._client._request("GET", "/v1/usage")).json()

    async def daily(self) -> dict[str, Any]:
        return (await self._client._request("GET", "/v1/usage/daily")).json()

    async def savings(self) -> dict[str, Any]:
        return (await self._client._request("GET", "/v1/usage/savings")).json()


class AsyncSecurHostClient:
    """Async twin of SecurHostClient.

    >>> async with AsyncSecurHostClient(api_key="nxs_live_...") as client:
    ...     reply = await client.chat.complete([{"role": "user", "content": "Hi"}])
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("An API key is required.")

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self._http = http_client or httpx.AsyncClient(timeout=timeout)

        self.chat = _AsyncChat(self)
        self.embeddings = _AsyncEmbeddings(self)
        self.usage = _AsyncUsage(self)
        self.job_agents = _AsyncJobAgents(self)

    async def __aenter__(self) -> AsyncSecurHostClient:
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.close()

    async def close(self) -> None:
        await self._http.aclose()

    def _headers(self) -> dict[str, str]:
        from securhost import __version__

        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"securhost-ai-python-async/{__version__}",
        }

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Retry the same cases the sync client does, with asyncio.sleep."""
        url = f"{self.base_url}{path}"
        last: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = await self._http.request(
                    method, url, headers=self._headers(), **kwargs
                )
            except httpx.HTTPError as exc:
                last = SecurHostConnectionError(f"Could not reach {url}: {exc}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self._backoff(attempt))
                    continue
                raise last from exc

            if response.status_code < 400:
                return response

            error = SecurHostClient._as_error(response)

            if error.retryable and attempt < self.max_retries:
                wait = getattr(error, "retry_after", None) or self._backoff(attempt)
                await asyncio.sleep(wait)
                last = error
                continue

            raise error

        raise last or SecurHostConnectionError("Request failed with no response")

    @staticmethod
    def _backoff(attempt: int) -> float:
        return min(2**attempt, 8) * (0.5 + random.random() / 2)  # noqa: S311


__all__ = ["AsyncSecurHostClient"]


# Backward compatibility alias
