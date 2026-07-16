"""SQL guardrails: parse-level validation before anything reaches BigQuery.

Proposal §5.3: permit SELECT only, explicitly reject write/DDL keywords,
allowlist datasets, and never rely on the prompt alone.  BigQuery's own
dry-run + maximum_bytes_billed provide the second layer (cost + syntax).
"""
import re
from dataclasses import dataclass, field

# Statements must start with SELECT or WITH (CTEs).
_ALLOWED_START = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)

# Any of these as standalone words -> reject. (Word-boundary match, so a
# column literally named `created_date` does not trip on CREATE.)
_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|CREATE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|"
    r"CALL|EXECUTE|BEGIN|COMMIT|ROLLBACK|EXPORT|LOAD)\b",
    re.IGNORECASE,
)

# Table references after FROM/JOIN: `project.dataset.table`, dataset.table etc.
_TABLE_REF = re.compile(
    r"\b(?:FROM|JOIN)\s+`?([A-Za-z0-9_\-\.]+)`?", re.IGNORECASE
)


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _strip_strings_and_comments(sql: str) -> str:
    """Remove string literals and comments so keyword scanning can't be spoofed
    or false-positive on text inside quotes."""
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"'(?:[^'\\]|\\.)*'", "''", sql)
    sql = re.sub(r'"(?:[^"\\]|\\.)*"', '""', sql)
    return sql


def validate_query(sql: str, allowed_datasets: tuple[str, ...]) -> ValidationResult:
    result = ValidationResult()
    if not sql or not sql.strip():
        result.errors.append("Empty query.")
        return result

    stripped = _strip_strings_and_comments(sql)

    if not _ALLOWED_START.match(stripped):
        result.errors.append("Only SELECT statements (optionally starting with WITH) are allowed.")

    # No multi-statement scripts.
    if stripped.rstrip().rstrip(";").count(";") > 0:
        result.errors.append("Multiple SQL statements are not allowed.")

    forbidden_hits = sorted({m.group(1).upper() for m in _FORBIDDEN.finditer(stripped)})
    if forbidden_hits:
        result.errors.append(f"Forbidden keywords: {', '.join(forbidden_hits)}. This tool is read-only.")

    # Dataset allowlist: every referenced table must be in an approved dataset.
    for m in _TABLE_REF.finditer(stripped):
        ref = m.group(1).strip(".")
        parts = ref.split(".")
        if len(parts) == 1:
            # bare table (or CTE name) - CTEs are fine; flag bare real tables as warning
            continue
        dataset = parts[-2]
        if dataset.upper() == "INFORMATION_SCHEMA":
            # allow schema introspection within allowed datasets
            dataset = parts[-3] if len(parts) >= 3 else dataset
        if dataset not in allowed_datasets and dataset.upper() != "INFORMATION_SCHEMA":
            result.errors.append(
                f"Table `{ref}` is outside the approved datasets ({', '.join(allowed_datasets)})."
            )

    if "select *" in stripped.lower():
        result.warnings.append(
            "SELECT * scans every column; select only the columns you need."
        )

    return result
