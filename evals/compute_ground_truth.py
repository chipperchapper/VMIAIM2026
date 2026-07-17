"""One streaming pass over ALL staged files -> evals/ground_truth.json.

Independent (pure Python, local files) source of expected values for the
benchmark and metric validation. Re-run whenever the staged data changes.
"""
import csv
import gzip
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STAGING = REPO / "data" / "staging"
OUT = REPO / "evals" / "ground_truth.json"

COMPETITIVE = {
    "FULL AND OPEN COMPETITION",
    "FULL AND OPEN COMPETITION AFTER EXCLUSION OF SOURCES",
    "COMPETED UNDER SAP",
}

files = sorted(STAGING.glob("FY*_097_Contracts_Full_*.csv.gz"))
if not files:
    sys.exit("no staged FY files found")
print(f"{len(files)} staged files")

csv.field_size_limit(2**31 - 1)

n = 0
contracts = set()
total = competitive = small = ffp = vet = woman = 0.0
small_txn = full_open_txn = 0
parents = defaultdict(float)
subs = defaultdict(float)
states = defaultdict(float)
months = defaultdict(float)
fy_dollars = defaultdict(float)
fy_rows = defaultdict(int)
biggest = (0.0, "", "")
min_date, max_date = "9999", "0000"

for path in files:
    print(f"  scanning {path.name}", flush=True)
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            n += 1
            v = float(r["federal_action_obligation"] or 0)
            total += v
            contracts.add(r["contract_award_unique_key"])
            if r["extent_competed"].strip() in COMPETITIVE:
                competitive += v
            if r["extent_competed"].strip() == "FULL AND OPEN COMPETITION":
                full_open_txn += 1
            if r["contracting_officers_determination_of_business_size"].strip() == "SMALL BUSINESS":
                small += v
                small_txn += 1
            if r["type_of_contract_pricing"].strip() == "FIRM FIXED PRICE":
                ffp += v
            if r["veteran_owned_business"] == "t":
                vet += v
            if r["woman_owned_business"] == "t":
                woman += v
            parents[r["recipient_parent_name"].strip()] += v
            subs[r["awarding_sub_agency_name"].strip()] += v
            states[r["primary_place_of_performance_state_code"].strip()] += v
            d = r["action_date"]
            if d:
                months[d[:7]] += v
                min_date, max_date = min(min_date, d), max(max_date, d)
            fy = r["action_date_fiscal_year"]
            fy_dollars[fy] += v
            fy_rows[fy] += 1
            if v > biggest[0]:
                biggest = (v, r["award_id_piid"], r["recipient_parent_name"].strip())

pos = [x for x in parents.values() if x > 0]
pos_total = sum(pos)
hhi = sum((x / pos_total) ** 2 for x in pos) * 10000

top = lambda d, k=5: sorted(((name, round(val, 2)) for name, val in d.items()),
                            key=lambda kv: -kv[1])[:k]

gt = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "files": [p.name for p in files],
    "transactions": n,
    "distinct_contracts": len(contracts),
    "total_obligations": round(total, 2),
    "top_parents": top(parents),
    "sub_agencies": top(subs, 10),
    "top_pop_states": top(states, 5),
    "monthly": {m: round(v, 2) for m, v in sorted(months.items())},
    "fiscal_year_dollars": {k: round(v, 2) for k, v in sorted(fy_dollars.items())},
    "fiscal_year_rows": dict(sorted(fy_rows.items())),
    "date_range": [min_date, max_date],
    "largest_transaction": {"amount": round(biggest[0], 2), "piid": biggest[1], "parent": biggest[2]},
    "full_open_transactions": full_open_txn,
    "small_business_transactions": small_txn,
    "firm_fixed_price_dollars": round(ffp, 2),
    "veteran_owned_dollars": round(vet, 2),
    "woman_owned_dollars": round(woman, 2),
    "metrics": {
        "competition_rate": competitive / total,
        "small_business_share": small / total,
        "contractor_concentration_hhi": hhi,
    },
}
OUT.write_text(json.dumps(gt, indent=2), encoding="utf-8")
print(json.dumps({k: gt[k] for k in ("transactions", "distinct_contracts", "total_obligations", "date_range")}, indent=1))
print(f"-> {OUT}")
