import os

import pytest

# CrewAI's anonymous telemetry stays off everywhere, including tests.
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")


@pytest.fixture
def ledger(tmp_path):
    """A fresh cost ledger per test, installed as the global one."""
    from safeflight.llm import Ledger, set_ledger

    led = Ledger(tmp_path / "state.db", max_usd_per_query=0.50, monthly_budget_usd=25.0)
    set_ledger(led)
    yield led
