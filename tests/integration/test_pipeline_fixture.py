"""The ingestion and scoring logic on a tiny synthetic database (fictional carriers), so CI
can test the pipeline without downloading the real datasets."""

import duckdb
import pandas as pd
import pytest

from data_pipeline.ingest import build_carrier_map, normalize
from safeflight.scoring.bayes import ScoringConfig
from safeflight.scoring.carriers import compute, load_inputs


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    c.execute("CREATE TABLE airlines (icao VARCHAR, iata VARCHAR, name VARCHAR, country VARCHAR)")
    c.execute(
        "INSERT INTO airlines VALUES ('MRD','MD','Meridian Air','United States'), "
        "('NWD','NW','Northwind Airways','United States')"
    )
    t100 = []
    for code, name, per_year in [
        ("MD", "Meridian Air", 300_000),
        ("NW", "Northwind Airways", 500_000),
        ("CL", "Coralline Airlines", 150_000),
        ("SR", "Saffron Regional", 20_000),
    ]:
        for year in range(2016, 2026):
            t100.append((year, 1, code, name, 1, "F", float(per_year)))
    c.register(
        "t",
        pd.DataFrame(
            t100,
            columns=["year", "month", "carrier", "carrier_name", "dot_id", "service_class", "departures"],
        ),
    )
    c.execute("CREATE TABLE t100_carrier_month AS SELECT * FROM t")
    c.execute(
        "CREATE TABLE events "
        "(ev_id VARCHAR, event_date DATE, event_type VARCHAR, severity VARCHAR, country VARCHAR)"
    )
    c.execute(
        "CREATE TABLE event_aircraft (ev_id VARCHAR, oper_code VARCHAR, oper_name VARCHAR, oper_dba VARCHAR)"
    )
    rows = [
        ("e1", "2024-03-01", "ACC", "serious", "MRDA", "Meridian Air Inc", None),  # designator match
        ("e2", "2023-05-01", "ACC", "minor", None, "NORTHWIND AIRWAYS, INC.", None),  # fuzzy match
        ("e3", "2022-07-01", "INC", "none", "NWDA", "Northwind Airways", None),  # incident: not scored
        ("e4", "2025-01-01", "ACC", "fatal", None, "Coralline Airlines Co", None),  # fuzzy match
        ("e5", "2021-01-01", "ACC", "minor", "ZZZA", "Unknown Charter LLC", None),  # unmapped
        ("e6", "2010-01-01", "ACC", "fatal", "MRDA", "Meridian Air Inc", None),  # outside window
        ("e7", "2024-06-01", "ACC", "fatal", "MRDA", "Meridian Air Inc", None),  # abroad: not scored
    ]
    for ev, d, t, s, code, name, dba in rows:
        country = "ESP" if ev == "e7" else "USA"
        c.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?)", [ev, d, t, s, country])
        c.execute("INSERT INTO event_aircraft VALUES (?, ?, ?, ?)", [ev, code, name, dba])
    return c


def test_normalize_strips_suffixes_and_punctuation():
    assert normalize("Delta Air Lines, Inc.") == "DELTA AIRLINES"
    assert normalize("NORTHWIND AIRWAYS, INC.") == "NORTHWIND AIRWAYS"


def test_carrier_map_methods(con):
    cmap = build_carrier_map(con).set_index("oper_name")
    assert cmap.loc["Meridian Air Inc", "carrier"] == "MD"
    assert cmap.loc["Meridian Air Inc", "method"] == "designator"
    assert cmap.loc["NORTHWIND AIRWAYS, INC.", "carrier"] == "NW"
    assert cmap.loc["NORTHWIND AIRWAYS, INC.", "method"] == "fuzzy"
    assert cmap.loc["Unknown Charter LLC", "method"] == "unmapped"
    assert pd.isna(cmap.loc["Unknown Charter LLC", "carrier"])


def test_scoring_uses_only_accidents_in_the_window(con):
    build_carrier_map(con)
    events, exposure, names = load_inputs(con, (2016, 2025))
    assert sorted(events) == ["CL", "MD", "NW"]
    assert len(events["MD"]) == 1  # 2010 event and the accident abroad excluded
    assert len(events["NW"]) == 1  # incident excluded
    _, _, scores = compute(events, exposure, (2016, 2025), ScoringConfig())
    by = {s.carrier: s for s in scores}
    assert by["SR"].weighted_events == 0
    assert by["SR"].band == "limited"  # small exposure: the prior dominates
    assert all(s.ci_low <= s.post_mean <= s.ci_high for s in scores)
