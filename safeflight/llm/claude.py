"""Claude for CrewAI agents.

`ClaudeLLM` subclasses CrewAI's native Anthropic provider (official `anthropic` SDK
underneath) so CrewAI keeps doing tool calling and message formatting. It adds one
interception point around the SDK client, where every request is adjusted and every
response is checked and costed:

Request (`prepare_request`, a pure function with unit tests):
- `output_config.effort` set per agent role (Opus 5.5 and Haiku 5.5 default to medium).
- Top-level `cache_control` so the stable prefix (system prompt, tools, history) is
  cached across the agent's tool-calling turns.
- Structured output moved to `output_config.format` (CrewAI still sends the deprecated
  beta `output_format`), and sampling parameters removed (current models reject them).
- Forced `tool_choice` (`any`/`tool`) relaxed to `auto`; Opus 5.5 returns 400 on it.
- On Opus 5.5, the server-side refusal fallback (`fallbacks: "default"`).

Response:
- Spend caps are checked before the call (`Ledger.check_budget`).
- Tokens (including cache reads and writes) and USD are written to the ledger.
- `stop_reason` is checked: `refusal` raises `LLMRefusal`, `max_tokens` raises
  `LLMTruncated`, so a cut-off or declined answer is never treated as complete.
"""

import json
from typing import Any

import crewai.llms.providers.anthropic.completion as _anthropic_completion
from crewai.llms.providers.anthropic.completion import AnthropicCompletion
from pydantic import Field, PrivateAttr

from safeflight.config import get_settings
from safeflight.llm.ledger import CallRecord, Ledger, now_ms
from safeflight.llm.prices import usd
from safeflight.llm.routing import route_for

STRUCTURED_OUTPUTS_BETA = "structured-outputs-2025-11-13"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
_CURRENT_MODELS = ("claude-haiku-5-5", "claude-opus-5-5", "claude-sonnet-5-5")

# CrewAI's provider only takes the native structured-output path for models it lists;
# for others it forces a tool call, which Opus 5.5 rejects. Every current model
# supports native structured outputs, so route them through the native path (which
# `prepare_request` then rewrites to the GA `output_config.format`).
_original_supports = _anthropic_completion._supports_native_structured_outputs


def _supports_native(model: str) -> bool:
    return model.lower().startswith(_CURRENT_MODELS) or _original_supports(model)


_anthropic_completion._supports_native_structured_outputs = _supports_native


class LLMRefusal(RuntimeError):
    """The model declined (stop_reason == "refusal")."""

    def __init__(self, category: str | None, explanation: str | None):
        super().__init__(f"model refused (category={category}): {explanation}")
        self.category = category


class LLMTruncated(RuntimeError):
    """The response hit max_tokens and is incomplete."""


def prepare_request(params: dict[str, Any], *, model: str, effort: str) -> dict[str, Any]:
    """Return the request to send, adjusted for current Claude models."""
    p = dict(params)
    for key in ("temperature", "top_p", "top_k"):
        p.pop(key, None)

    extra_body = dict(p.pop("extra_body", None) or {})
    output_config = dict(p.get("output_config") or {})
    output_config.setdefault("effort", effort)
    if fmt := extra_body.pop("output_format", None):
        output_config["format"] = fmt
    p["output_config"] = output_config

    betas = [b for b in (p.get("betas") or []) if b != STRUCTURED_OUTPUTS_BETA]

    tool_choice = p.get("tool_choice")
    if isinstance(tool_choice, dict) and tool_choice.get("type") in ("any", "tool"):
        p["tool_choice"] = {"type": "auto"}

    p.setdefault("cache_control", {"type": "ephemeral"})

    if model.startswith("claude-opus-5-5"):
        betas.append(FALLBACK_BETA)
        extra_body["fallbacks"] = "default"

    if betas:
        p["betas"] = betas
    else:
        p.pop("betas", None)
    if extra_body:
        p["extra_body"] = extra_body
    return p


class _MessagesProxy:
    """Stands in for `client.messages` / `client.beta.messages`."""

    def __init__(self, client: Any, owner: "ClaudeLLM"):
        self._client = client
        self._owner = owner

    def create(self, **params: Any) -> Any:
        return self._owner._send(self._client, params)

    def __getattr__(self, name: str) -> Any:  # count_tokens, stream, ...
        return getattr(self._client.messages, name)


class _BetaProxy:
    def __init__(self, client: Any, owner: "ClaudeLLM"):
        self.messages = _MessagesProxy(client, owner)
        self._client = client

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client.beta, name)


class _ClientProxy:
    def __init__(self, client: Any, owner: "ClaudeLLM"):
        self._client = client
        self.messages = _MessagesProxy(client, owner)
        self.beta = _BetaProxy(client, owner)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


_ledger: Ledger | None = None


def get_ledger() -> Ledger:
    global _ledger
    if _ledger is None:
        s = get_settings()
        _ledger = Ledger(
            s.state_db,
            max_usd_per_query=s.llm_max_usd_per_query,
            monthly_budget_usd=s.llm_monthly_budget_usd,
        )
    return _ledger


def set_ledger(ledger: Ledger) -> None:
    global _ledger
    _ledger = ledger


class ClaudeLLM(AnthropicCompletion):
    """CrewAI LLM for one agent role, e.g. ClaudeLLM.for_role("scout")."""

    role: str = Field(default="default")
    effort: str = Field(default="medium")
    _wrapped: Any = PrivateAttr(default=None)

    @classmethod
    def for_role(cls, role: str, **kwargs: Any) -> "ClaudeLLM":
        r = route_for(role)
        return cls(model=r.model, max_tokens=r.max_tokens, role=role, effort=r.effort, **kwargs)

    def _get_sync_client(self) -> Any:
        client = super()._get_sync_client()
        if self._wrapped is None or self._wrapped._client is not client:
            self._wrapped = _ClientProxy(client, self)
        return self._wrapped

    def _send(self, client: Any, params: dict[str, Any]) -> Any:
        ledger = get_ledger()
        ledger.check_budget()

        request = prepare_request(params, model=self.model, effort=self.effort)
        start = now_ms()
        if "betas" in request:
            response = client.beta.messages.create(**request)
        else:
            response = client.messages.create(**request)
        latency = now_ms() - start

        u = response.usage
        ins = int(getattr(u, "input_tokens", 0) or 0)
        outs = int(getattr(u, "output_tokens", 0) or 0)
        cw = int(getattr(u, "cache_creation_input_tokens", 0) or 0)
        cr = int(getattr(u, "cache_read_input_tokens", 0) or 0)
        served_by = getattr(response, "model", None) or self.model
        ledger.record(
            CallRecord(
                role=self.role,
                model=served_by,
                input_tokens=ins,
                output_tokens=outs,
                cache_write_tokens=cw,
                cache_read_tokens=cr,
                usd=usd(
                    served_by,
                    input_tokens=ins,
                    output_tokens=outs,
                    cache_write_tokens=cw,
                    cache_read_tokens=cr,
                ),
                stop_reason=response.stop_reason,
                latency_ms=latency,
            )
        )

        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            raise LLMRefusal(getattr(details, "category", None), getattr(details, "explanation", None))
        if response.stop_reason == "max_tokens":
            raise LLMTruncated(
                f"{self.role} hit max_tokens={request.get('max_tokens')}; raise it in routing.py"
            )
        return response


def describe_request(params: dict[str, Any]) -> str:
    """Stable JSON of a request, for debugging and tests."""
    return json.dumps(params, sort_keys=True, default=str)
