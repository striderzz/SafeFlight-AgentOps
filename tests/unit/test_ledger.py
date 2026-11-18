import pytest

from safeflight.llm.ledger import BudgetExceeded, CallRecord, Ledger, run_scope


def rec(usd: float) -> CallRecord:
    return CallRecord("scout", "claude-haiku-5-5", 100, 50, 0, 0, usd, "end_turn", 12.0)


def test_records_are_attributed_to_the_run(tmp_path):
    led = Ledger(tmp_path / "s.db", max_usd_per_query=1, monthly_budget_usd=10)
    with run_scope("run_a"):
        led.record(rec(0.01))
        led.record(rec(0.02))
    with run_scope("run_b"):
        led.record(rec(0.05))
    assert led.run_spend("run_a") == pytest.approx(0.03)
    assert [c["run_id"] for c in led.calls()] == ["run_a", "run_a", "run_b"]


def test_per_query_cap_blocks_the_next_call(tmp_path):
    led = Ledger(tmp_path / "s.db", max_usd_per_query=0.05, monthly_budget_usd=10)
    with run_scope("run_a"):
        led.check_budget()
        led.record(rec(0.05))
        with pytest.raises(BudgetExceeded, match="LLM_MAX_USD_PER_QUERY"):
            led.check_budget()
    with run_scope("run_b"):
        led.check_budget()  # a new query starts with a fresh cap


def test_monthly_cap_blocks_every_run(tmp_path):
    led = Ledger(tmp_path / "s.db", max_usd_per_query=100, monthly_budget_usd=0.10)
    with run_scope("run_a"):
        led.record(rec(0.10))
    with run_scope("run_b"), pytest.raises(BudgetExceeded, match="LLM_MONTHLY_BUDGET_USD"):
        led.check_budget()
