"""Repeatable ingestion for USAspending DoD contract archives.

Pipeline (proposal section 4.1: rerunnable, provenance-recorded, raw preserved):

    discover -> download -> trim -> manifest -> (optional) BigQuery load commands

  1. discover  Ask the USAspending API for the current FY2024/FY2025 DoD
               "Contracts_Full" archive URLs (filenames carry a refresh
               datestamp, so they must be discovered, not hardcoded).
  2. download  Stream each ~1.1 GB zip into data/downloads/ (skipped if the
               file already exists with the expected size). The zips are the
               immutable raw layer - never modified.
  3. trim      Stream each CSV inside the zip (without extracting to disk),
               keep only the 36 approved columns (docs/column-slice.md), and
               write gzipped CSVs to data/staging/.
  4. manifest  Record source URL, retrieval date, sizes, and row counts in
               data/manifest.json.
  5. load      Print (or run with --load) the `bq load` commands that push
               the staged files into the aim_raw dataset.

Usage:
    python ingest.py                # discover + download + trim + manifest
    python ingest.py --load         # ...and also run the bq load commands
    python ingest.py --dry-run      # discover only; print what would happen

No credentials are needed for anything except --load.
"""

import argparse
import csv
import gzip
import io
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests

# --- Configuration -----------------------------------------------------------

USASPENDING_API = "https://api.usaspending.gov/api/v2/bulk_download/list_monthly_files/"
DOD_AGENCY_DB_ID = 126     # USAspending internal id for Dept. of Defense (toptier code 097)
FISCAL_YEARS = [2024, 2025]

GCP_PROJECT = "vmi-aim-2026"
BQ_LOCATION = "US"
BQ_RAW_DATASET = "aim_raw"

BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
STAGING_DIR = BASE_DIR / "staging"
MANIFEST_PATH = BASE_DIR / "manifest.json"

# The approved 62-column slice. Rationale: docs/column-slice.md
# Verified against the USAspending data dictionary on 2026-07-14.
KEEP_COLUMNS = [
    # identity & keys
    "contract_transaction_unique_key",
    "contract_award_unique_key",
    "award_id_piid",
    "parent_award_id_piid",
    "modification_number",
    "award_or_idv_flag",
    # money
    "federal_action_obligation",
    "total_dollars_obligated",
    "current_total_value_of_award",
    "potential_total_value_of_award",
    # time
    "action_date",
    "action_date_fiscal_year",
    "period_of_performance_start_date",
    "period_of_performance_current_end_date",
    "period_of_performance_potential_end_date",
    # awarding side
    # (awarding_agency_name is NOT kept: it is constant "Department of Defense".
    #  trim() verifies that on every row, then drops it.)
    "awarding_sub_agency_name",
    "awarding_office_name",
    "funding_sub_agency_name",
    # recipient
    "recipient_uei",
    "recipient_name",
    "recipient_parent_uei",
    "recipient_parent_name",
    "recipient_city_name",
    "recipient_state_code",
    "recipient_country_name",
    # place of performance
    "primary_place_of_performance_city_name",
    "primary_place_of_performance_state_code",
    "primary_place_of_performance_country_name",
    # (dictionary lists this as primary_place_of_performance_congressional_district,
    #  but real download files use the newer name below)
    "prime_award_transaction_place_of_performance_cd_current",
    # what was bought
    "award_type",
    "transaction_description",
    "naics_code",
    "naics_description",
    "product_or_service_code",
    "product_or_service_code_description",
    # DoD programs & sourcing
    "dod_claimant_program_code",
    "dod_claimant_program_description",
    "dod_acquisition_program_code",
    "dod_acquisition_program_description",
    "foreign_funding",
    "foreign_funding_description",
    "country_of_product_or_service_origin",
    "place_of_manufacture",
    "national_interest_action",
    # competition
    "extent_competed",
    "solicitation_procedures",
    "number_of_offers_received",
    "type_of_set_aside",
    "type_of_contract_pricing",
    # flags
    "contracting_officers_determination_of_business_size",
    "action_type",
    "multi_year_contract",
    # business ownership & demographics
    "woman_owned_business",
    "veteran_owned_business",
    "service_disabled_veteran_owned_business",
    "minority_owned_business",
    "c8a_program_participant",
    "historically_underutilized_business_zone_hubzone_firm",
    "alaskan_native_corporation_owned_firm",
    "native_american_owned_business",
    "educational_institution",
    "nonprofit_organization",
]

# Long free-text fields (transaction_description) overflow the default limit.
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


# --- Steps -------------------------------------------------------------------

def discover(fiscal_year: int) -> dict:
    """Return {'file_name': ..., 'url': ...} for the current Contracts_Full archive."""
    resp = requests.post(
        USASPENDING_API,
        json={"agency": DOD_AGENCY_DB_ID, "fiscal_year": fiscal_year, "type": "contracts"},
        timeout=60,
    )
    resp.raise_for_status()
    for f in resp.json()["monthly_files"]:
        if "_Contracts_Full_" in f["file_name"]:
            return {"file_name": f["file_name"], "url": f["url"]}
    raise RuntimeError(f"No Contracts_Full archive found for FY{fiscal_year}")


def download(url: str, dest: Path) -> int:
    """Stream url to dest, skipping if already complete. Returns size in bytes."""
    head = requests.head(url, timeout=60, allow_redirects=True)
    head.raise_for_status()
    expected = int(head.headers.get("Content-Length", 0))

    if dest.exists() and expected and dest.stat().st_size == expected:
        print(f"  already downloaded ({expected:,} bytes) - skipping")
        return expected

    print(f"  downloading {expected / 1e9:.2f} GB ...")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        done = 0
        with open(dest, "wb") as out:
            for chunk in r.iter_content(chunk_size=1 << 20):
                out.write(chunk)
                done += len(chunk)
                if done % (200 << 20) < (1 << 20):  # progress every ~200 MB
                    print(f"    {done / 1e9:.2f} GB", flush=True)
    actual = dest.stat().st_size
    if expected and actual != expected:
        raise RuntimeError(f"Download incomplete: {actual} of {expected} bytes")
    return actual


DOD_AGENCY_NAME = "Department of Defense"


def trim(zip_path: Path) -> list[dict]:
    """Stream every CSV inside the zip, keep only KEEP_COLUMNS, write .csv.gz files.

    Also verifies awarding_agency_name == "Department of Defense" on every row
    (the column itself is constant, so it is verified here and then dropped
    rather than stored - see docs/column-slice.md).

    Returns one manifest entry per CSV part with row counts.
    """
    results = []
    with zipfile.ZipFile(zip_path) as zf:
        members = [m for m in zf.namelist() if m.lower().endswith(".csv")]
        if not members:
            raise RuntimeError(f"No CSV members found in {zip_path.name}")
        for member in members:
            out_path = STAGING_DIR / (Path(member).stem + ".csv.gz")
            print(f"  trimming {member} -> {out_path.name}")
            with zf.open(member) as raw:
                text = io.TextIOWrapper(raw, encoding="utf-8", newline="")
                reader = csv.DictReader(text)

                fieldnames = reader.fieldnames or []
                missing = [c for c in KEEP_COLUMNS if c not in fieldnames]
                if missing:
                    # Schema drift guard: fail loudly rather than silently
                    # writing empty columns.
                    raise RuntimeError(
                        f"{member} is missing expected columns: {missing}. "
                        "USAspending may have renamed fields - update KEEP_COLUMNS "
                        "and docs/column-slice.md."
                    )
                if "awarding_agency_name" not in fieldnames:
                    raise RuntimeError(
                        f"{member} has no awarding_agency_name column - cannot "
                        "verify the all-DoD assumption."
                    )

                rows = 0
                non_dod: dict[str, int] = {}
                with gzip.open(out_path, "wt", encoding="utf-8", newline="") as gz:
                    writer = csv.DictWriter(gz, fieldnames=KEEP_COLUMNS, extrasaction="ignore")
                    writer.writeheader()
                    for row in reader:
                        agency = row.get("awarding_agency_name", "")
                        if agency != DOD_AGENCY_NAME:
                            non_dod[agency] = non_dod.get(agency, 0) + 1
                        writer.writerow({c: row.get(c, "") for c in KEEP_COLUMNS})
                        rows += 1

            if non_dod:
                out_path.unlink(missing_ok=True)  # do not keep a bad staging file
                raise RuntimeError(
                    f"{member}: {sum(non_dod.values())} of {rows} rows are NOT "
                    f"Department of Defense: {non_dod}. The all-DoD assumption "
                    "is broken - investigate before loading."
                )

            results.append({
                "source_member": member,
                "staged_file": out_path.name,
                "rows": rows,
                "verified_all_dod": True,
                "staged_bytes": out_path.stat().st_size,
            })
            print(f"    {rows:,} rows (all verified DoD)")
    return results


def bq_load_commands(staged_files_by_fy: dict[int, list[str]]) -> list[str]:
    """One `bq load` per staged part; parts append into one table per fiscal year."""
    cmds = []
    for fy, files in staged_files_by_fy.items():
        table = f"{GCP_PROJECT}:{BQ_RAW_DATASET}.dod_contracts_fy{fy}"
        for i, name in enumerate(files):
            replace_flag = "--replace" if i == 0 else "--noreplace"
            cmds.append(
                f"bq load --project_id={GCP_PROJECT} --location={BQ_LOCATION} "
                f"--source_format=CSV --skip_leading_rows=1 --autodetect "
                f"--allow_quoted_newlines {replace_flag} "
                f"{table} {STAGING_DIR / name}"
            )
    return cmds


# --- Main --------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="discover only")
    parser.add_argument("--load", action="store_true", help="run bq load after staging")
    args = parser.parse_args()

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    STAGING_DIR.mkdir(parents=True, exist_ok=True)

    manifest = {
        "dataset": "USAspending DoD prime contract transactions",
        "license": "US Government work - public domain",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "columns_kept": len(KEEP_COLUMNS),
        "fiscal_years": {},
    }
    staged_by_fy: dict[int, list[str]] = {}

    for fy in FISCAL_YEARS:
        print(f"\nFY{fy}")
        info = discover(fy)
        print(f"  current archive: {info['file_name']}")
        if args.dry_run:
            continue

        zip_path = DOWNLOAD_DIR / info["file_name"]
        size = download(info["url"], zip_path)
        parts = trim(zip_path)

        manifest["fiscal_years"][str(fy)] = {
            "source_url": info["url"],
            "archive_file": info["file_name"],
            "archive_bytes": size,
            "parts": parts,
            "total_rows": sum(p["rows"] for p in parts),
        }
        staged_by_fy[fy] = [p["staged_file"] for p in parts]

    if args.dry_run:
        print("\nDry run complete - nothing downloaded.")
        return

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nManifest written to {MANIFEST_PATH}")

    print("\nBigQuery load commands:")
    for cmd in bq_load_commands(staged_by_fy):
        print(f"  {cmd}")
        if args.load:
            import subprocess
            subprocess.run(cmd, shell=True, check=True)

    if not args.load:
        print("\n(re-run with --load to execute these once GCP access is ready)")


if __name__ == "__main__":
    main()
