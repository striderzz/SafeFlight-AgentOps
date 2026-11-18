"""Which model and effort each agent role uses. One place to read and change routing."""

from dataclasses import dataclass

from safeflight.config import get_settings


@dataclass(frozen=True)
class Route:
    model: str
    effort: str  # low | medium | high | xhigh | max
    max_tokens: int


def route_for(role: str) -> Route:
    s = get_settings()
    fast, strong = s.model_fast, s.model_strong
    table = {
        "scout": Route(fast, "low", 4000),
        "researcher": Route(fast, "medium", 8000),
        "airspace": Route(fast, "low", 4000),
        "analyst": Route(strong, "medium", 8000),
        "advisor": Route(fast, "medium", 8000),
        "advisor_escalation": Route(strong, "high", 8000),
        "judge": Route(fast, "low", 2000),
    }
    if role not in table:
        raise KeyError(f"unknown agent role {role!r}; add it to safeflight/llm/routing.py")
    return table[role]
