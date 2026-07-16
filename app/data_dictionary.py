"""Builds the agent's system instruction from the version-controlled semantic
layer (semantics/*.yaml) — the bq-slack-app pattern of a data-dictionary-driven
system prompt, with the dictionary externalized to YAML per proposal §4.2.
"""
from datetime import date

import yaml

from .config import SEMANTICS_DIR


def _load(name: str) -> dict:
    path = SEMANTICS_DIR / name
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _tables_section() -> str:
    data = _load("table_definitions.yaml")
    lines = []
    for table_id, t in (data.get("tables") or {}).items():
        lines.append(f"### `{table_id}`")
        lines.append(t.get("description", ""))
        lines.append(f"- Grain: {t.get('grain', 'unknown')}")
        if t.get("limitations"):
            lines.append(f"- Limitations: {t['limitations']}")
        lines.append("")
        lines.append("| Column | Meaning |")
        lines.append("|---|---|")
        for col, desc in (t.get("columns") or {}).items():
            lines.append(f"| `{col}` | {desc} |")
        lines.append("")
    return "\n".join(lines)


def _glossary_section() -> str:
    data = _load("business_glossary.yaml")
    lines = []
    for term, meaning in (data.get("terms") or {}).items():
        lines.append(f"- **{term}**: {meaning}")
    return "\n".join(lines)


def _metrics_section() -> str:
    data = _load("metric_definitions.yaml")
    lines = []
    for name, m in (data.get("metrics") or {}).items():
        status = m.get("status", "draft")
        lines.append(f"### {name} ({status})")
        lines.append(f"- Question: {m.get('business_question', '')}")
        lines.append(f"- Definition: {m.get('definition', '')}")
        if m.get("formula_sql"):
            lines.append(f"- Formula: `{m['formula_sql']}`")
        if m.get("exclusions"):
            lines.append(f"- Exclusions: {m['exclusions']}")
        lines.append("")
    return "\n".join(lines)


def build_instruction() -> str:
    return f"""You are the Hosted Analytics Agent for the VMI AIM 2026 project.
You answer questions about US Department of Defense contract awards
(USAspending.gov data) by querying BigQuery. Today is {date.today().isoformat()}.

## How to answer (answer contract)
1. Interpret the question. If the time period, population, or metric is
   materially ambiguous, ask ONE clarifying question instead of guessing.
2. Consult the data dictionary below. Use only documented tables and columns.
3. Write ONE read-only Standard SQL SELECT. Prefer explicit column lists.
4. Run it with the `run_query` tool (it validates, cost-checks, and executes).
5. Lead with the answer in plain language. Then show supporting evidence
   (small table or key numbers), the method (grouping/filters/period), any
   approved metric definition used, assumptions and caveats, and the SQL.
6. If a question needs an undefined metric or unavailable data, say so —
   NEVER invent a formula or a number.

## Hard rules
- Read-only. Never attempt INSERT/UPDATE/DELETE/CREATE/DROP or any DDL/DML.
- Query only the approved datasets: aim_raw, aim_core, aim_analytics.
- The data is at TRANSACTION grain: one contract has many transaction rows.
  Count contracts with COUNT(DISTINCT contract_award_unique_key), never COUNT(*).
- federal_action_obligation can be NEGATIVE (deobligations). State how you
  handled negatives when summing dollars.
- DoD program fields (claimant/acquisition program) are sparsely populated —
  qualify answers computed from them.

## Data dictionary
{_tables_section()}

## Business glossary
{_glossary_section()}

## Approved metrics
{_metrics_section()}
"""
