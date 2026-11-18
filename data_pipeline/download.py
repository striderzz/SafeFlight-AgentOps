"""Download the public source files into data/raw/ (gitignored).

Sources (licences recorded in README):
- NTSB aviation accident database, avall.zip (US government public data)
- OpenFlights airlines.dat, airports.dat, planes.dat (ODbL)
- BTS T-100 Segment (All Carriers): see data_pipeline/t100.py (form-based)

A file is skipped when it already exists with the size the server reports, so reruns
only fetch what changed.

Usage: python -m data_pipeline.download
"""

import sys
from pathlib import Path

import httpx

RAW = Path("data/raw")
USER_AGENT = "SafeFlight-AgentOps/0.1 (portfolio research project)"

SOURCES = {
    "ntsb/avall.zip": "https://data.ntsb.gov/avdata/FileDirectory/DownloadFile?fileID=C%3A%5Cavdata%5Cavall.zip",
    "openflights/airlines.dat": "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airlines.dat",
    "openflights/airports.dat": "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat",
    "openflights/planes.dat": "https://raw.githubusercontent.com/jpatokal/openflights/master/data/planes.dat",
}


def fetch(client: httpx.Client, url: str, dest: Path) -> str:
    head = client.head(url)
    size = int(head.headers.get("content-length", -1))
    if dest.exists() and dest.stat().st_size == size:
        return f"unchanged  {dest} ({size:,} bytes)"
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with client.stream("GET", url) as r, tmp.open("wb") as f:
        r.raise_for_status()
        for chunk in r.iter_bytes(1 << 20):
            f.write(chunk)
    tmp.replace(dest)
    return f"downloaded {dest} ({dest.stat().st_size:,} bytes)"


def main(names: list[str]) -> None:
    with httpx.Client(follow_redirects=True, timeout=600, headers={"User-Agent": USER_AGENT}) as client:
        for rel, url in SOURCES.items():
            if names and not any(n in rel for n in names):
                continue
            print(fetch(client, url, RAW / rel), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
