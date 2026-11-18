"""Build data/safeflight.duckdb from the raw files in data/raw/.

Tables (see INFO.md, Data model):
- airlines, airports, aircraft_types   OpenFlights reference data
- events, event_aircraft, findings,     NTSB accidents and incidents for airline
  narratives                            operations (FAR Part 121 and 129)
- t100_carrier_month                    BTS T-100 departures per carrier and month
- carrier_map                           NTSB operator -> BTS carrier, with how it matched
- data_snapshots                        one row per build, with a hash of the inputs

Usage: python -m data_pipeline.ingest [--db data/safeflight.duckdb]
"""

import argparse
import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd
from rapidfuzz import fuzz, process

RAW = Path("data/raw")
DEFAULT_DB = Path("data/safeflight.duckdb")
AIRLINE_PARTS = ("121", "129")  # US air carriers, foreign air carriers operating in the US
ALIASES = Path(__file__).with_name("carrier_aliases.csv")
FUZZY_MIN = 90
DESIGNATOR_NAME_MIN = 60


# ---------- OpenFlights ----------


def load_openflights(con: duckdb.DuckDBPyConnection, root: Path) -> None:
    na = ["\\N", ""]
    airlines = pd.read_csv(
        root / "airlines.dat",
        header=None,
        na_values=na,
        keep_default_na=False,
        names=["openflights_id", "name", "alias", "iata", "icao", "callsign", "country", "active"],
        dtype=str,
    )
    airlines = airlines[airlines.icao.notna() & (airlines.icao.str.len() == 3)]
    airports = pd.read_csv(
        root / "airports.dat",
        header=None,
        na_values=na,
        keep_default_na=False,
        names=[
            "openflights_id",
            "name",
            "city",
            "country",
            "iata",
            "icao",
            "lat",
            "lon",
            "alt_ft",
            "utc_offset",
            "dst",
            "tz",
            "type",
            "source",
        ],
        dtype={"iata": str, "icao": str},
    )
    airports = airports[airports.iata.notna() & (airports.iata.str.len() == 3)]
    planes = pd.read_csv(  # noqa: F841 - read by DuckDB by name in the SQL below
        root / "planes.dat", header=None, na_values=na, names=["name", "iata", "icao"], dtype=str
    )
    con.execute("CREATE OR REPLACE TABLE airlines AS SELECT * FROM airlines")
    con.execute(
        "CREATE OR REPLACE TABLE airports AS "
        "SELECT iata, icao, name, city, country, lat, lon, tz FROM airports"
    )
    con.execute("CREATE OR REPLACE TABLE aircraft_types AS SELECT * FROM planes")


# ---------- NTSB ----------


def read_ntsb(mdb: Path) -> dict[str, pd.DataFrame]:
    from access_parser import AccessParser

    db = AccessParser(str(mdb))
    return {t: pd.DataFrame(db.parse_table(t)) for t in ("events", "aircraft", "Findings", "narratives")}


def severity(highest_injury: object) -> str:
    code = highest_injury.strip() if isinstance(highest_injury, str) else ""
    return {"FATL": "fatal", "SERS": "serious", "MINR": "minor"}.get(code, "none")


def load_ntsb(con: duckdb.DuckDBPyConnection, tables: dict[str, pd.DataFrame]) -> None:
    ac = tables["aircraft"].copy()
    ac["far_part"] = ac["far_part"].astype(str).str.strip()
    ac = ac[ac.far_part.isin(AIRLINE_PARTS)]
    ev = tables["events"]
    ev = ev[ev.ev_id.isin(ac.ev_id)].copy()
    ev["event_date"] = pd.to_datetime(ev.ev_date, errors="coerce").dt.date
    ev["severity"] = ev.ev_highest_injury.map(severity)
    events = ev[
        [
            "ev_id",
            "ntsb_no",
            "event_date",
            "ev_type",
            "ev_country",
            "ev_city",
            "severity",
            "inj_tot_f",
            "inj_tot_s",
        ]
    ].rename(columns={"ev_type": "event_type", "ev_country": "country", "ev_city": "city"})

    for col in ("oper_name", "oper_code", "oper_dba", "acft_make", "acft_model", "damage", "regis_no"):
        ac[col] = ac[col].astype("string").str.strip()
    aircraft = ac[
        [
            "ev_id",
            "Aircraft_Key",
            "far_part",
            "oper_name",
            "oper_code",
            "oper_dba",
            "acft_make",
            "acft_model",
            "damage",
            "regis_no",
        ]
    ].rename(columns={"Aircraft_Key": "aircraft_key", "acft_make": "make", "acft_model": "model"})

    fi = tables["Findings"]
    findings = fi[fi.ev_id.isin(ac.ev_id)][
        ["ev_id", "Aircraft_Key", "finding_no", "finding_code", "finding_description", "Cause_Factor"]
    ].rename(columns={"Aircraft_Key": "aircraft_key", "Cause_Factor": "cause_factor"})

    na = tables["narratives"]
    narratives = na[na.ev_id.isin(ac.ev_id)][
        ["ev_id", "Aircraft_Key", "narr_accp", "narr_accf", "narr_cause"]
    ]
    narratives = narratives.rename(
        columns={
            "Aircraft_Key": "aircraft_key",
            "narr_accp": "preliminary",
            "narr_accf": "factual",
            "narr_cause": "cause",
        }
    )

    for name, df in (
        ("events", events),
        ("event_aircraft", aircraft),
        ("findings", findings),
        ("narratives", narratives),
    ):
        con.register("df", df)
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM df")
        con.unregister("df")


# ---------- BTS T-100 ----------


def load_t100(con: duckdb.DuckDBPyConnection, root: Path) -> None:
    files = sorted(root.glob("t100_segment_all_*.csv"))
    if not files:
        raise FileNotFoundError(f"no T-100 files in {root}; run python -m data_pipeline.t100")
    glob = (root / "t100_segment_all_*.csv").as_posix()
    con.execute(
        f"""
        CREATE OR REPLACE TABLE t100_carrier_month AS
        SELECT CAST(YEAR AS INT) AS year, CAST(MONTH AS INT) AS month,
               UNIQUE_CARRIER AS carrier, any_value(UNIQUE_CARRIER_NAME) AS carrier_name,
               CAST(AIRLINE_ID AS INT) AS dot_id, CLASS AS service_class,
               SUM(CAST(DEPARTURES_PERFORMED AS DOUBLE)) AS departures
        FROM read_csv('{glob}', header = true, all_varchar = true)
        WHERE DEPARTURES_PERFORMED IS NOT NULL
        GROUP BY ALL
        """
    )


# ---------- carrier matching ----------

_SUFFIXES = r"\b(INC|CORP|CORPORATION|CO|COMPANY|LLC|LTD|LIMITED|PLC|SA|AG|DBA|THE)\b"


def _text(value: object) -> str:
    """A string, or "" for None, NaN and pandas NA (missing values from the source data)."""
    return value.strip() if isinstance(value, str) else ""


def normalize(name: str | None) -> str:
    if not name:
        return ""
    s = name.upper().replace("AIR LINES", "AIRLINES").replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(_SUFFIXES, " ", s)
    return re.sub(r"\s+", " ", s).strip()


def build_carrier_map(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Map each NTSB operator to a BTS carrier code.

    1. Designator: the first three letters of NTSB `oper_code` (FAA certificate designator)
       are often the ICAO airline code; OpenFlights gives its IATA code, which BTS uses.
       FAA designators are not always ICAO codes (American Eagle's AEAA would hit Air
       Europa's AEA), so the match only counts when the names also agree.
    2. Alias table: hand-checked names in carrier_aliases.csv (mergers, renames).
    3. Fuzzy name match against BTS carrier names, accepted at score >= FUZZY_MIN.
    Anything else stays unmapped and is reported, never guessed.
    """
    ops = con.execute("SELECT DISTINCT oper_code, oper_name, oper_dba FROM event_aircraft").df()
    icao_info = {
        icao: (iata, country)
        for icao, iata, country in con.execute(
            "SELECT icao, iata, country FROM airlines WHERE iata IS NOT NULL AND iata <> ''"
        ).fetchall()
    }
    bts = con.execute(
        "SELECT carrier, any_value(carrier_name) FROM t100_carrier_month "
        "WHERE carrier IS NOT NULL GROUP BY carrier"
    ).fetchall()
    bts_name_by_code = {c: normalize(_text(n)) for c, n in bts}
    bts_names = {normalize(_text(n)): c for c, n in bts if _text(n)}
    aliases = {}
    if ALIASES.exists():
        a = pd.read_csv(ALIASES, dtype=str)
        aliases = {normalize(r.ntsb_name): r.bts_carrier for r in a.itertuples()}

    rows = []
    for op in ops.itertuples():
        code = _text(op.oper_code)[:3].upper()
        norm = normalize(_text(op.oper_name) or _text(op.oper_dba))
        carrier, method, score = None, "unmapped", None
        iata, country = icao_info.get(code, (None, None)) if code else (None, None)
        if iata and iata in bts_name_by_code:
            if norm:
                agree = fuzz.token_set_ratio(norm, bts_name_by_code[iata])
            else:
                # no name to check: trust the designator only for US airlines (Part 121
                # operators); a foreign ICAO code here is a coincidence, not a match
                agree = 100.0 if country == "United States" else 0.0
            if agree >= DESIGNATOR_NAME_MIN:
                carrier, method, score = iata, "designator", float(agree)
        if carrier is None and norm in aliases:
            carrier, method = aliases[norm], "alias"
        if carrier is None and norm:
            hit = process.extractOne(norm, list(bts_names), scorer=fuzz.token_sort_ratio)
            if hit and hit[1] >= FUZZY_MIN:
                carrier, method, score = bts_names[hit[0]], "fuzzy", float(hit[1])
        rows.append(
            {
                "oper_code": op.oper_code,
                "oper_name": op.oper_name,
                "oper_dba": op.oper_dba,
                "carrier": carrier,
                "method": method,
                "score": score,
            }
        )
    df = pd.DataFrame(rows)
    con.register("df", df)
    con.execute("CREATE OR REPLACE TABLE carrier_map AS SELECT * FROM df")
    con.unregister("df")
    return df


def sources_hash(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        st = p.stat()
        h.update(f"{p.name}:{st.st_size}:{int(st.st_mtime)}".encode())
    return h.hexdigest()[:16]


def main(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    load_openflights(con, RAW / "openflights")
    print("openflights loaded", flush=True)
    load_ntsb(con, read_ntsb(RAW / "ntsb" / "avall.mdb"))
    print("ntsb loaded", flush=True)
    load_t100(con, RAW / "t100")
    print("t100 loaded", flush=True)
    cmap = build_carrier_map(con)
    inputs = [*RAW.glob("openflights/*.dat"), RAW / "ntsb" / "avall.mdb", *RAW.glob("t100/*.csv")]
    con.execute(
        "CREATE TABLE IF NOT EXISTS data_snapshots "
        "(snapshot_id VARCHAR, created_at TIMESTAMP, sources_hash VARCHAR)"
    )
    snap = sources_hash(inputs)
    con.execute(
        "INSERT INTO data_snapshots VALUES (?, ?, ?)", [snap, datetime.now(UTC).replace(tzinfo=None), snap]
    )
    for t in (
        "airlines",
        "airports",
        "events",
        "event_aircraft",
        "findings",
        "narratives",
        "t100_carrier_month",
    ):
        print(f"{t:20} {con.execute(f'SELECT count(*) FROM {t}').fetchone()[0]:>9,}")
    print("carrier_map methods:", cmap.method.value_counts().to_dict())
    con.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    main(ap.parse_args().db)
