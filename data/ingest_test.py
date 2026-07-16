"""Test-slice ingestion: 3 months of DoD contract transactions.

Uses USAspending's custom-download API to generate a filtered extract
(awarding agency = Department of Defense, action_date in a 3-month window),
then reuses the production trim logic from ingest.py so the test run
exercises the same column slice and staging format as the full pipeline.

Usage:
    python ingest_test.py          # request, poll, download, trim
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from ingest import (
    BQ_LOCATION,
    BQ_RAW_DATASET,
    DOWNLOAD_DIR,
    GCP_PROJECT,
    STAGING_DIR,
    trim,
)

REQUEST_API = "https://api.usaspending.gov/api/v2/bulk_download/awards/"
STATUS_API = "https://api.usaspending.gov/api/v2/download/status"

START_DATE = "2025-01-01"
END_DATE = "2025-03-31"
TEST_TABLE = "dod_contracts_test"

BASE_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = BASE_DIR / "manifest_test.json"


def request_extract() -> dict:
    payload = {
        "filters": {
            "prime_award_types": ["A", "B", "C", "D"],  # contract award types
            "agencies": [
                {"type": "awarding", "tier": "toptier", "name": "Department of Defense"}
            ],
            "date_type": "action_date",
            "date_range": {"start_date": START_DATE, "end_date": END_DATE},
        },
        "file_format": "csv",
    }
    resp = requests.post(REQUEST_API, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()


def poll_until_ready(file_name: str, timeout_s: int = 1800) -> dict:
    started = time.time()
    while True:
        resp = requests.get(STATUS_API, params={"file_name": file_name}, timeout=60)
        resp.raise_for_status()
        status = resp.json()
        state = status.get("status")
        elapsed = int(time.time() - started)
        print(f"  [{elapsed:>4}s] status: {state}", flush=True)
        if state == "finished":
            return status
        if state == "failed":
            raise RuntimeError(f"USAspending reported failure: {status.get('message')}")
        if elapsed > timeout_s:
            raise TimeoutError(f"Extract not ready after {timeout_s}s")
        time.sleep(15)


def download(url: str, dest: Path) -> int:
    print(f"  downloading -> {dest.name}")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as out:
            for chunk in r.iter_content(chunk_size=1 << 20):
                out.write(chunk)
    return dest.stat().st_size


def main() -> None:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    STAGING_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Requesting DoD contract extract {START_DATE} .. {END_DATE}")
    job = request_extract()
    file_name = job["file_name"]
    print(f"  job accepted: {file_name}")

    status = poll_until_ready(file_name)
    file_url = status.get("file_url") or job.get("file_url")

    zip_path = DOWNLOAD_DIR / file_name
    size = download(file_url, zip_path)
    print(f"  downloaded {size / 1e6:.1f} MB")

    parts = trim(zip_path)

    manifest = {
        "purpose": "3-month test slice for pipeline validation",
        "filters": {"awarding_toptier": "Department of Defense",
                    "date_type": "action_date",
                    "start_date": START_DATE, "end_date": END_DATE},
        "source_url": file_url,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "archive_bytes": size,
        "parts": parts,
        "total_rows": sum(p["rows"] for p in parts),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nTotal rows: {manifest['total_rows']:,}")
    print(f"Manifest: {MANIFEST_PATH}")

    print("\nBigQuery load commands:")
    table = f"{GCP_PROJECT}:{BQ_RAW_DATASET}.{TEST_TABLE}"
    for i, p in enumerate(parts):
        replace_flag = "--replace" if i == 0 else "--noreplace"
        print(
            f"  bq load --project_id={GCP_PROJECT} --location={BQ_LOCATION} "
            f"--source_format=CSV --skip_leading_rows=1 --autodetect "
            f"--allow_quoted_newlines {replace_flag} "
            f"{table} {STAGING_DIR / p['staged_file']}"
        )


if __name__ == "__main__":
    main()
