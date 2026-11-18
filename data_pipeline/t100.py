"""Download BTS T-100 Segment (All Carriers), one zipped CSV per year, into data/raw/t100/.

BTS publishes T-100 only through an ASP.NET download form on TranStats, so this script
loads the form, copies its hidden state fields, ticks the columns SafeFlight needs and
submits it for one year at a time. If BTS changes the form this breaks loudly (no zip in
the response); the fallback is downloading the same columns by hand into data/raw/t100/.

Usage: python -m data_pipeline.t100 2016 2025
"""

import io
import re
import sys
import zipfile
from pathlib import Path

import httpx

FORM_URL = "https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FMG&QO_fu146_anzr=Nv4%20Pn44vr45"
OUT = Path("data/raw/t100")
USER_AGENT = "SafeFlight-AgentOps/0.1 (portfolio research project)"

COLUMNS = [
    "YEAR",
    "MONTH",
    "UNIQUE_CARRIER",
    "UNIQUE_CARRIER_NAME",
    "CARRIER",
    "AIRLINE_ID",
    "ORIGIN",
    "DEST",
    "ORIGIN_COUNTRY",
    "DEST_COUNTRY",
    "AIRCRAFT_TYPE",
    "CLASS",
    "DEPARTURES_PERFORMED",
]


def hidden_fields(html: str) -> dict[str, str]:
    fields = {}
    for name in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"):
        m = re.search(rf'name="{name}"[^>]*value="([^"]*)"', html) or re.search(
            rf'value="([^"]*)"[^>]*name="{name}"', html
        )
        if not m:
            raise RuntimeError(f"form field {name} not found; the BTS form may have changed")
        fields[name] = m.group(1)
    return fields


def download_year(client: httpx.Client, year: int) -> Path:
    dest = OUT / f"t100_segment_all_{year}.csv"
    if dest.exists() and dest.stat().st_size > 0:
        print(f"unchanged  {dest}")
        return dest
    form = client.get(FORM_URL)
    form.raise_for_status()
    data = hidden_fields(form.text) | {
        "cboGeography": "All",
        "cboYear": str(year),
        "cboPeriod": "All",
        "chkDownloadZip": "on",
        "btnDownload": "Download",
    }
    data |= {col: "on" for col in COLUMNS}
    r = client.post(FORM_URL, data=data)
    r.raise_for_status()
    if not r.content.startswith(b"PK"):
        raise RuntimeError(f"{year}: expected a zip, got {r.headers.get('content-type')}")
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        # the zip can also hold a small field-definitions CSV; the data is the largest one
        csvs = [i for i in z.infolist() if i.filename.lower().endswith(".csv")]
        csv_name = max(csvs, key=lambda i: i.file_size).filename
        OUT.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(z.read(csv_name))
    print(f"downloaded {dest} ({dest.stat().st_size:,} bytes)")
    return dest


def main(first: int, last: int) -> None:
    with httpx.Client(follow_redirects=True, timeout=900, headers={"User-Agent": USER_AGENT}) as client:
        for year in range(first, last + 1):
            download_year(client, year)


if __name__ == "__main__":
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 2016
    b = int(sys.argv[2]) if len(sys.argv) > 2 else a
    main(a, b)
