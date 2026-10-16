"""Model access (design D8). The only module that knows about a provider (MNT-2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .result import Usage

MAX_TOKENS = 4000  # includes any model reasoning


@dataclass
class Completion:
    text: str
    stop_reason: str
    usage: Usage


class LLM(Protocol):
    def complete(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, str]],
        model_params: dict[str, Any],
    ) -> Completion: ...


class BedrockLLM:
    """AWS Bedrock Converse API, which accepts any Bedrock model family.

    Credentials come from the standard AWS chain (OIDC in CI). No sampling parameters are sent:
    newer Claude models reject them. Model-specific options go through `model_params`.
    """

    def __init__(self, region: str | None = None):
        import boto3
        from botocore.config import Config

        self._client = boto3.client(
            "bedrock-runtime",
            region_name=region,
            config=Config(
                connect_timeout=10,
                read_timeout=120,
                retries={"mode": "adaptive", "max_attempts": 3},
            ),
        )

    def complete(self, *, model, system, messages, model_params) -> Completion:
        request: dict[str, Any] = {
            "modelId": model,
            "system": [{"text": system}],
            "messages": [{"role": m["role"], "content": [{"text": m["text"]}]} for m in messages],
            "inferenceConfig": {"maxTokens": MAX_TOKENS},
        }
        if model_params:
            request["additionalModelRequestFields"] = model_params
        resp = self._client.converse(**request)
        blocks = resp.get("output", {}).get("message", {}).get("content", [])
        usage = resp.get("usage", {})
        return Completion(
            # Only text blocks are the answer; reasoning blocks are skipped.
            text="".join(b["text"] for b in blocks if "text" in b),
            stop_reason=resp.get("stopReason", ""),
            usage=Usage(usage.get("inputTokens", 0), usage.get("outputTokens", 0)),
        )
