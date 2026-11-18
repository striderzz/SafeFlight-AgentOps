# How it works: data and the carrier score (Phases 2 and 3)

## Sources (downloaded into the gitignored `data/raw/`)

| Source | File | Licence or terms |
|---|---|---|
| NTSB aviation accident database | `avall.zip` (97 MB, Access database, 2008 onward) | US government public data |
| BTS T-100 Segment (All Carriers), 2016 to 2025 | one CSV per year, about 35 MB each | US government public data |
| OpenFlights | `airlines.dat`, `airports.dat`, `planes.dat` | Open Database License (ODbL) |

`python -m data_pipeline.download` fetches NTSB and OpenFlights. BTS publishes T-100 only through an ASP.NET form, so `python -m data_pipeline.t100 2016 2025` loads the form, copies its hidden state fields, ticks the needed columns and submits it once per year. The zip also holds a small field-definitions CSV, so the script keeps the largest CSV.

## Ingestion (`python -m data_pipeline.ingest`)

- The NTSB Access file is read with the pure-Python `access-parser`, so it works on Windows, macOS and Linux without an ODBC driver. Only FAR Part 121 (US airlines) and Part 129 (foreign airlines in the US) flights are kept.
- T-100 rows are summed to departures per carrier, month and service class.
- **Carrier matching**, NTSB operator to BTS carrier code:
  1. *Designator:* the first three letters of the FAA certificate designator (`UALA`, `SWAA`) are often the ICAO code; OpenFlights gives the IATA code BTS uses. Because FAA designators are not always ICAO codes (American Eagle's `AEAA` collides with Air Europa's `AEA`), the match counts only if the names also agree, or, with no name, only for a US airline.
  2. *Alias table* (`carrier_aliases.csv`): mergers and renames, such as Chautauqua into Republic (BTS `YX`).
  3. *Fuzzy name match* (rapidfuzz, score 90 or more).
  Unmatched operators are recorded as unmapped, never guessed.
- Result: 262 of 275 US Part 121/129 accidents in 2016 to 2025 are attributed to a carrier (`docs/results/scoring/coverage.json`).

## The score (`python -m safeflight.scoring.carriers`)

Exactly the method in INFO.md, Scoring method: severity and recency weights, recency-weighted exposure, a Gamma-Poisson model with an empirical Bayes prior (method of moments, checked by maximum likelihood), the posterior mean and its 90% interval. Results are in `carrier_scores` and `docs/results/scoring/`.

**Finding.** The between-carrier variance estimate hit its floor and the ML fit agreed: in this window, US carriers' accident rates do not differ beyond chance. The 13 largest carriers are all Typical; the rest have under 1 million weighted departures and are Limited data; the severity-weight sensitivity check changes no bands. The product reports this instead of ranking airlines on noise.

## Tests

- Unit tests check the math against hand-computed values and the worked example, prior recovery on simulated data, and the floor on homogeneous data.
- A synthetic fixture database tests matching rules, US-only and accidents-only filtering, and the window.
- Real-data tests (`tests/data/`, skipped in CI) check row counts, the Part 121/129 filter, orphan keys, attribution of at least 90% of accidents, and that the ten largest US carriers are scored.
