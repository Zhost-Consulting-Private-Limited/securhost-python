"""
Data types for the SecurHost SDK.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping


@dataclass(frozen=True)
class Cost:
    """The cost accounting attached to one gateway response."""
    amount: Decimal
    currency: str
    original: Decimal
    saved: Decimal
    model: str = ""
    model_requested: str = ""
    rerouted: bool = False
    reported: bool = True

    @classmethod
    def from_headers(cls, headers: Mapping[str, str]) -> Cost:
        def _get(keys: list[str]) -> str | None:
            for k in keys:
                if k in headers:
                    return headers[k]
                if k.lower() in headers:
                    return headers[k.lower()]
            return None

        def _dec(keys: list[str], default: str = "0.0") -> Decimal:
            val = _get(keys)
            if not val:
                return Decimal(default)
            try:
                return Decimal(val)
            except Exception:
                return Decimal(default)

        reported = bool(
            _get(["X-SecurHost-Cost", "X-SecurHost-Cost-Usd"]) is not None
            or _get(["X-SecurHost-Cost-Original", "X-SecurHost-Original-Cost-Usd"]) is not None
            or _get(["X-SecurHost-Saved", "X-SecurHost-Savings-Usd"]) is not None
        )

        amount = _dec(["X-SecurHost-Cost", "X-SecurHost-Cost-Usd"], "0.0")
        original = _dec(["X-SecurHost-Cost-Original", "X-SecurHost-Original-Cost-Usd"], "0.0")
        
        saved_str = _get(["X-SecurHost-Saved", "X-SecurHost-Savings-Usd"])
        if saved_str:
            try:
                saved = Decimal(saved_str)
            except Exception:
                saved = max(Decimal("0.0"), original - amount)
        elif reported:
            saved = max(Decimal("0.0"), original - amount)
        else:
            saved = Decimal("0.0")

        model = _get(["X-SecurHost-Model", "X-SecurHost-Model-Served"]) or ""
        model_requested = _get(["X-SecurHost-Model-Requested"]) or ""
        rerouted = bool(model and model_requested and model != model_requested)
        currency = _get(["X-SecurHost-Currency"]) or "USD"

        return cls(
            amount=amount,
            currency=currency,
            original=original,
            saved=saved,
            model=model,
            model_requested=model_requested,
            rerouted=rerouted,
            reported=reported,
        )


@dataclass(frozen=True)
class Usage:
    """Token usage counters."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    @classmethod
    def from_envelope(cls, body: dict[str, Any]) -> Usage:
        usage = body.get("usage") or {}
        return cls(
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            total_tokens=int(usage.get("total_tokens") or 0),
        )


@dataclass(frozen=True)
class ChatResponse:
    """A completed chat turn."""
    raw: dict[str, Any]
    usage: Usage
    cost: Cost
    request_id: str

    @property
    def output_text(self) -> str:
        choices = self.raw.get("choices") or []
        if not choices:
            return ""
        return choices[0].get("message", {}).get("content") or ""

    @property
    def tool_calls(self) -> list[dict[str, Any]]:
        choices = self.raw.get("choices") or []
        if not choices:
            return []
        return choices[0].get("message", {}).get("tool_calls") or []

    @property
    def model(self) -> str:
        return self.raw.get("model") or ""


@dataclass(frozen=True)
class EmbeddingResponse:
    """Vector embeddings response."""
    raw: dict[str, Any]
    usage: Usage
    cost: Cost
    request_id: str

    @property
    def embeddings(self) -> list[list[float]]:
        data = self.raw.get("data") or []
        return [item.get("embedding", []) for item in data]
