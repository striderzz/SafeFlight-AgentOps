"""Cost log and spend caps.

Every Claude call is written to the `llm_calls` table in SQLite with its run id, agent
role, model, token counts (including cache reads and writes), USD cost, stop reason and
latency. Before each call the ledger checks two caps: spend for the current run (one
user query) and spend for the current calendar month.
"""

import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

current_run_id: ContextVar[str | None] = ContextVar("current_run_id", default=None)


class BudgetExceeded(RuntimeError):
    """A spend cap would be crossed; the call is not made."""


@contextmanager
def run_scope(run_id: str) -> Iterator[None]:
    """Attribute every LLM call inside the block to one run (one user query)."""
    token = current_run_id.set(run_id)
    try:
        yield
    finally:
        current_run_id.reset(token)


@dataclass
class CallRecord:
    role: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int
    usd: float
    stop_reason: str | None
    latency_ms: float


_SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_calls (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                 TEXT NOT NULL,
    run_id             TEXT,
    role               TEXT NOT NULL,
    model              TEXT NOT NULL,
    input_tokens       INTEGER NOT NULL,
    output_tokens      INTEGER NOT NULL,
    cache_write_tokens INTEGER NOT NULL,
    cache_read_tokens  INTEGER NOT NULL,
    usd                REAL NOT NULL,
    stop_reason        TEXT,
    latency_ms         REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS llm_calls_run ON llm_calls (run_id);
CREATE INDEX IF NOT EXISTS llm_calls_ts ON llm_calls (ts);
"""


class Ledger:
    def __init__(self, path: Path | str, *, max_usd_per_query: float, monthly_budget_usd: float):
        self.max_usd_per_query = max_usd_per_query
        self.monthly_budget_usd = monthly_budget_usd
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)

    def run_spend(self, run_id: str) -> float:
        with self._lock:
            row = self._conn.execute(
                "SELECT COALESCE(SUM(usd), 0) FROM llm_calls WHERE run_id = ?", (run_id,)
            ).fetchone()
        return float(row[0])

    def month_spend(self, now: datetime | None = None) -> float:
        now = now or datetime.now(UTC)
        month = now.strftime("%Y-%m")
        with self._lock:
            row = self._conn.execute(
                "SELECT COALESCE(SUM(usd), 0) FROM llm_calls WHERE substr(ts, 1, 7) = ?", (month,)
            ).fetchone()
        return float(row[0])

    def check_budget(self) -> None:
        """Raise BudgetExceeded when the run or the month has used its cap."""
        run_id = current_run_id.get()
        if run_id is not None and self.run_spend(run_id) >= self.max_usd_per_query:
            raise BudgetExceeded(
                f"run {run_id} reached its ${self.max_usd_per_query:.2f} cap (LLM_MAX_USD_PER_QUERY)"
            )
        if self.month_spend() >= self.monthly_budget_usd:
            raise BudgetExceeded(
                f"monthly LLM budget of ${self.monthly_budget_usd:.2f} reached (LLM_MONTHLY_BUDGET_USD)"
            )

    def record(self, rec: CallRecord) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO llm_calls (ts, run_id, role, model, input_tokens, output_tokens, "
                "cache_write_tokens, cache_read_tokens, usd, stop_reason, latency_ms) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    datetime.now(UTC).isoformat(timespec="milliseconds"),
                    current_run_id.get(),
                    rec.role,
                    rec.model,
                    rec.input_tokens,
                    rec.output_tokens,
                    rec.cache_write_tokens,
                    rec.cache_read_tokens,
                    rec.usd,
                    rec.stop_reason,
                    rec.latency_ms,
                ),
            )
            self._conn.commit()

    def calls(self, run_id: str | None = None) -> list[dict]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM llm_calls WHERE (? IS NULL OR run_id = ?) ORDER BY id",
                (run_id, run_id),
            )
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


def now_ms() -> float:
    return time.perf_counter() * 1000
