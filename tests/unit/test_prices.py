import pytest

from safeflight.llm.prices import price_for, usd


def test_haiku_cost_per_million_tokens():
    # 1M uncached input + 1M output on Haiku 5.5 = $0.10 + $0.50
    assert usd("claude-haiku-5-5", input_tokens=1_000_000, output_tokens=1_000_000) == pytest.approx(0.60)


def test_cache_reads_and_writes_are_priced_separately():
    cost = usd(
        "claude-opus-5-5",
        input_tokens=1_000,
        output_tokens=500,
        cache_write_tokens=10_000,
        cache_read_tokens=100_000,
    )
    expected = (1_000 * 4.00 + 500 * 20.00 + 10_000 * 5.00 + 100_000 * 0.20) / 1_000_000
    assert cost == pytest.approx(expected)


def test_unknown_model_fails_loudly():
    with pytest.raises(KeyError):
        price_for("claude-unknown-1")
