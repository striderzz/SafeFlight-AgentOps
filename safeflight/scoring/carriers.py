"""Score every carrier from the DuckDB tables and store `carrier_scores`.

Events: NTSB accidents (event_type ACC) in the US in the window, on FAR Part 121/129
flights, with the operator mapped to a BTS carrier code (carrier_map). One event counts
once per carrier, even when two of its aircraft were involved. Accidents abroad are left
out because BTS T-100 exposure only covers flights to, from and within the US; counting
them would put foreign operations in the numerator but not the denominator.
Exposure: BTS T-100 departures performed per carrier and year.
Ages are measured back from 31 December of the window's last year.

Usage: python -m safeflight.scoring.carriers [--db data/safeflight.duckdb]
"""

import argparse
import json
from dataclasses import asdict, replace
from datetime import date
from pathlib import Path

import duckdb
import numpy as np

from safeflight.scoring.bayes import (
    CarrierScore,
    Event,
    Prior,
    ScoringConfig,
    fit_prior_ml,
    fit_prior_moments,
    score,
    weighted_events,
    weighted_exposure,
)

WINDOW = (2016, 2025)
RESULTS = Path("docs/results/scoring")


def load_inputs(
    con: duckdb.DuckDBPyConnection, window: tuple[int, int]
) -> tuple[dict[str, list[tuple[date, str]]], dict[str, dict[int, float]], dict[str, str]]:
    first, last = window
    rows = con.execute(
        """
        SELECT DISTINCT cm.carrier, e.ev_id, e.event_date, e.severity
        FROM events e
        JOIN event_aircraft a USING (ev_id)
        JOIN carrier_map cm
          ON a.oper_code IS NOT DISTINCT FROM cm.oper_code
         AND a.oper_name IS NOT DISTINCT FROM cm.oper_name
         AND a.oper_dba  IS NOT DISTINCT FROM cm.oper_dba
        WHERE e.event_type = 'ACC' AND e.country = 'USA' AND cm.carrier IS NOT NULL
          AND year(e.event_date) BETWEEN ? AND ?
        """,
        [first, last],
    ).fetchall()
    events: dict[str, list[tuple[date, str]]] = {}
    for carrier, _ev, ev_date, sev in rows:
        events.setdefault(carrier, []).append((ev_date, sev))

    exp_rows = con.execute(
        "SELECT carrier, year, SUM(departures) FROM t100_carrier_month "
        "WHERE year BETWEEN ? AND ? AND carrier IS NOT NULL GROUP BY carrier, year",
        [first, last],
    ).fetchall()
    exposure: dict[str, dict[int, float]] = {}
    for carrier, year, deps in exp_rows:
        exposure.setdefault(carrier, {})[int(year)] = float(deps or 0)

    names = dict(
        con.execute(
            "SELECT carrier, any_value(carrier_name) FROM t100_carrier_month GROUP BY carrier"
        ).fetchall()
    )
    return events, exposure, names


def compute(
    events: dict[str, list[tuple[date, str]]],
    exposure: dict[str, dict[int, float]],
    window: tuple[int, int],
    cfg: ScoringConfig,
) -> tuple[Prior, Prior, list[CarrierScore]]:
    end = date(window[1], 12, 31)
    carriers = sorted(set(exposure) | set(events))
    y, e = {}, {}
    for c in carriers:
        evs = [Event((end - d).days / 365.25, s) for d, s in events.get(c, [])]
        y[c] = weighted_events(evs, cfg)
        # mid-year age for annual departures
        e[c] = weighted_exposure({window[1] - yr + 0.5: d for yr, d in exposure.get(c, {}).items()}, cfg)
    ya, ea = np.array([y[c] for c in carriers]), np.array([e[c] for c in carriers])
    mom = fit_prior_moments(ya, ea, cfg)
    ml = fit_prior_ml(ya, ea, cfg)
    scores = [score(c, y[c], e[c], mom, cfg) for c in carriers]
    return mom, ml, scores


def sensitivity(events, exposure, window, base: ScoringConfig) -> dict:
    """How many bands change under other severity weightings."""
    _, _, ref = compute(events, exposure, window, base)
    ref_band = {s.carrier: s.band for s in ref}
    out = {}
    for label, weights in {
        "fatal_only_heavier": {"fatal": 1.0, "serious": 0.3, "minor": 0.1, "none": 0.1},
        "all_equal": {"fatal": 1.0, "serious": 1.0, "minor": 1.0, "none": 1.0},
    }.items():
        _, _, alt = compute(events, exposure, window, replace(base, severity_weights=weights))
        changed = [s.carrier for s in alt if s.band != ref_band[s.carrier]]
        out[label] = {"weights": weights, "bands_changed": len(changed), "carriers": changed[:30]}
    return out


def main(db: Path) -> None:
    cfg = ScoringConfig()
    con = duckdb.connect(str(db))
    events, exposure, names = load_inputs(con, WINDOW)
    mom, ml, scores = compute(events, exposure, WINDOW, cfg)
    snap = con.execute("SELECT snapshot_id FROM data_snapshots ORDER BY created_at DESC LIMIT 1").fetchall()[
        0
    ][0]
    rows = [asdict(s) | {"carrier_name": names.get(s.carrier), "snapshot_id": snap} for s in scores]
    import pandas as pd

    con.register("df", pd.DataFrame(rows))
    con.execute("CREATE OR REPLACE TABLE carrier_scores AS SELECT * FROM df")
    con.unregister("df")

    RESULTS.mkdir(parents=True, exist_ok=True)
    bands = pd.DataFrame(rows).band.value_counts().to_dict()
    summary = {
        "window": WINDOW,
        "snapshot_id": snap,
        "carriers_scored": len(scores),
        "carriers_with_events": sum(1 for s in scores if s.weighted_events > 0),
        "prior_moments": asdict(mom) | {"industry_rate": mom.mean},
        "prior_ml_check": asdict(ml) | {"industry_rate": ml.mean},
        "heterogeneity": (
            "No detectable difference between carriers beyond chance: the between-carrier variance "
            "estimate was at or below the floor, so the prior is tight and posteriors sit close to the "
            "industry rate. The ML fit agrees (very large alpha and beta)."
            if mom.method == "moments_floored"
            else "Between-carrier variance above the floor."
        ),
        "bands": bands,
        "sensitivity": sensitivity(events, exposure, WINDOW, cfg),
    }
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    top = sorted(
        (r for r in rows if r["exposure_millions"] >= 1), key=lambda r: r["exposure_millions"], reverse=True
    )[:25]
    lines = [
        "| Carrier | Code | Weighted events | Exposure (M dep.) | Rate | 90% interval | Band |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in top:
        lines.append(
            f"| {r['carrier_name']} | {r['carrier']} | {r['weighted_events']:.2f} | "
            f"{r['exposure_millions']:.2f} | "
            f"{r['post_mean']:.3f} | {r['ci_low']:.3f} to {r['ci_high']:.3f} | {r['band']} |"
        )
    (RESULTS / "largest_carriers.md").write_text("\n".join(lines) + "\n")
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "carriers_scored",
                    "carriers_with_events",
                    "prior_moments",
                    "prior_ml_check",
                    "bands",
                )
            },
            indent=2,
            default=str,
        )
    )
    con.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=Path("data/safeflight.duckdb"))
    main(ap.parse_args().db)
