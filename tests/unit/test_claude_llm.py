"""ClaudeLLM against a fake SDK client: what is sent, what is logged, what is refused."""

from types import SimpleNamespace

import pytest
from anthropic.types import Message, TextBlock, Usage

from safeflight.llm import ClaudeLLM, LLMRefusal, LLMTruncated, run_scope
from safeflight.llm.prices import usd


def message(text="ok", stop_reason="end_turn", model="claude-haiku-5-5", **usage):
    u = {
        "input_tokens": 120,
        "output_tokens": 30,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }
    u.update(usage)
    return Message.model_construct(
        id="msg_test",
        type="message",
        role="assistant",
        model=model,
        content=[TextBlock(type="text", text=text)],
        stop_reason=stop_reason,
        stop_sequence=None,
        stop_details=SimpleNamespace(category="cyber", explanation="declined")
        if stop_reason == "refusal"
        else None,
        usage=Usage.model_construct(**u),
    )


class FakeMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.sent = []

    def create(self, **params):
        self.sent.append(params)
        return self.responses.pop(0)


def install(llm, responses):
    fake = SimpleNamespace(messages=FakeMessages(responses))
    fake.beta = SimpleNamespace(messages=fake.messages)
    llm._client = fake
    return fake.messages


@pytest.fixture
def scout():
    return ClaudeLLM.for_role("scout", api_key="test-key-not-real")


def test_call_returns_text_and_logs_cost(scout, ledger):
    sent = install(scout, [message("found 5 itineraries", cache_read_input_tokens=900)])
    with run_scope("run_1"):
        out = scout.call("find flights BOM to LHR")
    assert out == "found 5 itineraries"

    req = sent.sent[0]
    assert req["model"] == "claude-haiku-5-5"
    assert req["output_config"]["effort"] == "low"
    assert req["cache_control"] == {"type": "ephemeral"}

    [row] = ledger.calls("run_1")
    assert row["role"] == "scout" and row["cache_read_tokens"] == 900
    assert row["usd"] == pytest.approx(
        usd("claude-haiku-5-5", input_tokens=120, output_tokens=30, cache_read_tokens=900)
    )


def test_refusal_raises_and_is_still_logged(scout, ledger):
    install(scout, [message("", stop_reason="refusal")])
    with run_scope("run_2"), pytest.raises(LLMRefusal) as err:
        scout.call("x")
    assert err.value.category == "cyber"
    assert ledger.calls("run_2")[0]["stop_reason"] == "refusal"


def test_truncated_answer_is_not_treated_as_complete(scout, ledger):
    install(scout, [message("partial", stop_reason="max_tokens")])
    with run_scope("run_3"), pytest.raises(LLMTruncated):
        scout.call("x")


def test_budget_cap_stops_the_call_before_it_is_sent(scout, ledger):
    sent = install(scout, [message("a"), message("b")])
    ledger.max_usd_per_query = 0.0
    with run_scope("run_4"), pytest.raises(Exception, match="cap"):
        scout.call("x")
    assert sent.sent == []


def test_routing_uses_opus_with_fallback_for_the_analyst(ledger):
    analyst = ClaudeLLM.for_role("analyst", api_key="test-key-not-real")
    sent = install(analyst, [message("scored", model="claude-opus-5-5")])
    with run_scope("run_5"):
        analyst.call("score MD")
    req = sent.sent[0]
    assert req["model"] == "claude-opus-5-5"
    assert req["betas"] == ["server-side-fallback-2026-07-01"]
    assert req["extra_body"] == {"fallbacks": "default"}
