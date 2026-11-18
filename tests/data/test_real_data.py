"""Data-quality checks on the real database (data/safeflight.duckdb).

Skipped when the database has not been built (CI uses the synthetic fixture instead).
Build it with: python -m data_pipeline.download && python -m data_pipeline.t100 2016 2025
&& python -m data_pipeline.ingest && python -m safeflight.scoring.carriers
"""

from pathlib import Path

import duckdb
import pytest

DB = Path("data/safeflight.duckdb")
pytestmark = pytest.mark.skipif(not DB.exists(), reason="real database not built")

LARGEST_US_CARRIERS = ["WN", "AA", "DL", "UA", "OO", "B6", "AS", "NK", "YX", "MQ"]


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect(str(DB), read_only=True)
    yield c
    c.close()


def one(con, sql, *params):
    return con.execute(sql, list(params)).fetchall()[0][0]


def test_row_counts_in_expected_ranges(con):
    assert 5_000 < one(con, "SELECT count(*) FROM airlines") < 10_000
    assert 5_000 < one(con, "SELECT count(*) FROM airports") < 10_000
    assert 1_000 < one(con, "SELECT count(*) FROM events") < 5_000
    assert one(con, "SELECT count(DISTINCT year) FROM t100_carrier_month") == 10


def test_only_airline_operations_are_kept(con):
    parts = {r[0] for r in con.execute("SELECT DISTINCT far_part FROM event_aircraft").fetchall()}
    assert parts <= {"121", "129"}


def test_no_orphan_keys(con):
    assert (
        one(
            con,
            "SELECT count(*) FROM event_aircraft a LEFT JOIN events e USING (ev_id) WHERE e.ev_id IS NULL",
        )
        == 0
    )
    assert (
        one(con, "SELECT count(*) FROM narratives n LEFT JOIN events e USING (ev_id) WHERE e.ev_id IS NULL")
        == 0
    )


def test_largest_carriers_are_mapped_and_scored(con):
    scored = {
        r[0] for r in con.execute("SELECT carrier FROM carrier_scores WHERE band <> 'limited'").fetchall()
    }
    missing = [c for c in LARGEST_US_CARRIERS if c not in scored]
    assert not missing, f"not scored with enough exposure: {missing}"


def test_most_us_accidents_are_attributed(con):
    total, mapped = con.execute(
        """
        SELECT count(DISTINCT e.ev_id), count(DISTINCT CASE WHEN cm.carrier IS NOT NULL THEN e.ev_id END)
        FROM events e JOIN event_aircraft a USING (ev_id)
        JOIN carrier_map cm ON a.oper_code IS NOT DISTINCT FROM cm.oper_code
          AND a.oper_name IS NOT DISTINCT FROM cm.oper_name AND a.oper_dba IS NOT DISTINCT FROM cm.oper_dba
        WHERE e.event_type = 'ACC' AND e.country = 'USA' AND year(e.event_date) BETWEEN 2016 AND 2025
        """
    ).fetchall()[0]
    assert mapped / total >= 0.9


def test_scores_are_well_formed(con):
    assert (
        one(
            con,
            "SELECT count(*) FROM carrier_scores WHERE NOT (ci_low <= post_mean AND post_mean <= ci_high)",
        )
        == 0
    )
    assert (
        one(
            con,
            "SELECT count(*) FROM carrier_scores WHERE band NOT IN ('strong','typical','higher','limited')",
        )
        == 0
    )
