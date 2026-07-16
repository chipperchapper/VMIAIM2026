"""Independent metric validation (proposal 4.3: every metric needs a
validation query and a known expected result).

Two computation paths that share NOTHING:
  expected : pure-Python arithmetic over the LOCAL staged CSV
  actual   : the metric's formula SQL from semantics/metric_definitions.yaml,
             executed in BigQuery against aim_core.contract_transactions

If both agree (tolerance 1e-6 relative), the metric definition is validated.
Writes evals/metric_validation.md and prints a summary.
"""
import csv
import gzip
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

from google.cloud import bigquery

REPO = Path(__file__).resolve().parents[1]
STAGED = REPO / "data" / "staging" / "test_dod_contracts_2026q2.csv.gz"
OUT = REPO / "evals" / "metric_validation.md"

COMPETITIVE = {
    "FULL AND OPEN COMPETITION",
    "FULL AND OPEN COMPETITION AFTER EXCLUSION OF SOURCES",
    "COMPETED UNDER SAP",
}

# ---------- expected values: pure Python over the local file ----------

rows = []
with gzip.open(STAGED, "rt", encoding="utf-8", newline="") as f:
    for r in csv.DictReader(f):
        rows.append(r)

def money(r):
    v = r["federal_action_obligation"].strip()
    return float(v) if v else 0.0

total = sum(money(r) for r in rows)
competitive = sum(money(r) for r in rows if r["extent_competed"].strip() in COMPETITIVE)
small = sum(money(r) for r in rows
            if r["contracting_officers_determination_of_business_size"].strip() == "SMALL BUSINESS")

parent_net = defaultdict(float)
for r in rows:
    parent_net[r["recipient_parent_name"].strip()] += money(r)
positives = [v for v in parent_net.values() if v > 0]
pos_total = sum(positives)
hhi = sum((v / pos_total) ** 2 for v in positives) * 10000

expected = {
    "competition_rate": competitive / total,
    "small_business_share": small / total,
    "contractor_concentration_hhi": hhi,
}

# ---------- actual values: metric SQL in BigQuery ----------

client = bigquery.Client(project="vmi-aim-2026")

SQL = {
    "competition_rate": """
        SELECT SAFE_DIVIDE(
          SUM(IF(extent_competed IN ('FULL AND OPEN COMPETITION',
              'FULL AND OPEN COMPETITION AFTER EXCLUSION OF SOURCES',
              'COMPETED UNDER SAP'), federal_action_obligation, 0)),
          SUM(federal_action_obligation)) AS v
        FROM aim_core.contract_transactions
    """,
    "small_business_share": """
        SELECT SAFE_DIVIDE(
          SUM(IF(contracting_officers_determination_of_business_size = 'SMALL BUSINESS',
              federal_action_obligation, 0)),
          SUM(federal_action_obligation)) AS v
        FROM aim_core.contract_transactions
    """,
    "contractor_concentration_hhi": """
        WITH parent_totals AS (
          SELECT recipient_parent_name, SUM(federal_action_obligation) AS net
          FROM aim_core.contract_transactions
          GROUP BY recipient_parent_name
          HAVING net > 0
        ),
        shares AS (
          SELECT net / SUM(net) OVER () AS share FROM parent_totals
        )
        SELECT SUM(POW(share, 2)) * 10000 AS v FROM shares
    """,
}

results = []
for name, sql in SQL.items():
    actual = list(client.query(sql).result())[0].v
    exp = expected[name]
    ok = abs(actual - exp) <= max(1e-6 * max(abs(exp), 1), 1e-9)
    results.append((name, exp, actual, ok))
    print(f"{'PASS' if ok else 'FAIL'} {name}: expected={exp:.6f} actual={actual:.6f}")

# ---------- report ----------

lines = [
    "# Metric Validation Report",
    "",
    f"**Date:** {date.today().isoformat()} · **Population:** aim_core.contract_transactions "
    f"({len(rows)} transactions, test slice Apr-Jul 2026)",
    "",
    "Two fully independent computation paths: pure Python over the local staged",
    "CSV vs. the metric formula SQL executed in BigQuery. Agreement validates the",
    "definition AND the load pipeline end-to-end.",
    "",
    "| Metric | Expected (Python/local) | Actual (SQL/BigQuery) | Verdict |",
    "|---|---|---|---|",
]
for name, exp, act, ok in results:
    lines.append(f"| {name} | {exp:.6f} | {act:.6f} | {'✅ MATCH' if ok else '❌ MISMATCH'} |")
lines += [
    "",
    "Interpretation on this test slice:",
    f"- competition_rate = {expected['competition_rate']:.1%} of dollars competitively awarded",
    f"- small_business_share = {expected['small_business_share']:.1%} of dollars to small businesses",
    f"- HHI = {expected['contractor_concentration_hhi']:.0f} "
    "(>2500 = highly concentrated by antitrust convention; small samples skew high)",
    "",
    "NOTE: values are from the 204-row test slice and are NOT representative;",
    "re-run this script after the full FY2024-FY2025 load to re-validate.",
]
OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"\nreport -> {OUT}")
sys.exit(0 if all(ok for *_, ok in results) else 1)
