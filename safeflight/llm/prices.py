"""Per-token prices in US dollars per million tokens (Anthropic first-party API).

Cache writes use the 5-minute TTL rate (1.25x input). Cache reads are the published
rate per model. Update this table when prices change; every cost figure in the logs is
computed from it, so a wrong row means wrong costs.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Price:
    input: float
    output: float
    cache_write: float
    cache_read: float


PRICES: dict[str, Price] = {
    # Haiku 5.5 rates apply to prompts up to 100K tokens; SafeFlight prompts stay far below.
    "claude-haiku-5-5": Price(input=0.10, output=0.50, cache_write=0.125, cache_read=0.01),
    "claude-opus-5-5": Price(input=4.00, output=20.00, cache_write=5.00, cache_read=0.20),
}


def price_for(model: str) -> Price:
    for name, price in PRICES.items():
        if model.startswith(name):
            return price
    raise KeyError(f"no price for model {model!r}; add it to safeflight/llm/prices.py")


def usd(
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
    cache_write_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float:
    """Cost of one call. `input_tokens` is the uncached input, as the API reports it."""
    p = price_for(model)
    total = (
        input_tokens * p.input
        + output_tokens * p.output
        + cache_write_tokens * p.cache_write
        + cache_read_tokens * p.cache_read
    )
    return total / 1_000_000
