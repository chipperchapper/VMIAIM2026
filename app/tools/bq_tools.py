"""BigQuery tools for the ADK agent.

ADK convention: plain typed functions with docstrings; the docstring is the
tool description the model sees. Safety mirrors bq-slack-app:

  1. query_validator: SELECT-only, dataset allowlist, no multi-statements
  2. BigQuery dry-run first: syntax + bytes-scanned estimate
  3. maximum_bytes_billed + timeout + row cap on real execution
  4. DRY_RUN/LIVE safety switch (LIVE requires explicit env opt-in)
  5. every call audited to logs/audit.jsonl
"""
import time
from typing import Any

from google.cloud import bigquery
from google.cloud.exceptions import GoogleCloudError

from ..audit import AuditLogger, RateLimiter
from ..config import CONFIG, logger
from ..query_validator import validate_query

_audit = AuditLogger()
_rate_limiter = RateLimiter()
_client: bigquery.Client | None = None


def _bq() -> bigquery.Client:
    global _client
    if _client is None:
        _client = bigquery.Client(project=CONFIG.project_id, location=CONFIG.bq_location)
        logger.info("BigQuery client created for %s", CONFIG.project_id)
    return _client


def _fmt_bytes(n: int) -> str:
    for unit, div in (("GB", 1e9), ("MB", 1e6), ("KB", 1e3)):
        if n >= div:
            return f"{n / div:.2f} {unit}"
    return f"{n} bytes"


def list_tables(dataset: str) -> dict[str, Any]:
    """List all tables in one of the approved BigQuery datasets.

    Args:
        dataset: Dataset name. Must be one of: aim_raw, aim_core, aim_analytics.

    Returns:
        dict with 'tables' (list of table names) or 'error'.
    """
    if dataset not in CONFIG.allowed_datasets:
        return {"status": "error",
                "error": f"Dataset '{dataset}' is not approved. Allowed: {list(CONFIG.allowed_datasets)}"}
    try:
        tables = [t.table_id for t in _bq().list_tables(dataset)]
    except GoogleCloudError as e:
        return {"status": "error", "error": str(e)}
    _audit.log("list_tables", dataset=dataset, count=len(tables))
    return {"status": "success", "dataset": dataset, "tables": tables}


def show_schema(table: str) -> dict[str, Any]:
    """Show the live column schema (names, types, modes) for a BigQuery table.

    Args:
        table: Table reference as 'dataset.table', e.g. 'aim_raw.dod_contracts_test'.

    Returns:
        dict with 'columns' (list of {name, type, mode}) or 'error'.
    """
    parts = table.split(".")
    if len(parts) != 2:
        return {"status": "error", "error": "Use dataset.table format, e.g. aim_raw.dod_contracts_test"}
    dataset, table_id = parts
    if dataset not in CONFIG.allowed_datasets:
        return {"status": "error",
                "error": f"Dataset '{dataset}' is not approved. Allowed: {list(CONFIG.allowed_datasets)}"}
    try:
        t = _bq().get_table(f"{CONFIG.project_id}.{dataset}.{table_id}")
    except GoogleCloudError as e:
        return {"status": "error", "error": str(e)}
    _audit.log("show_schema", table=table)
    return {
        "status": "success",
        "table": table,
        "row_count": t.num_rows,
        "columns": [{"name": f.name, "type": f.field_type, "mode": f.mode or "NULLABLE"}
                    for f in t.schema],
    }


def run_query(sql: str) -> dict[str, Any]:
    """Validate and execute one read-only Standard SQL SELECT against BigQuery.

    The query is checked against safety rules (SELECT-only, approved datasets),
    dry-run for cost, then executed with a hard bytes-billed cap, timeout, and
    row limit. In DRY_RUN mode the query is validated but NOT executed.

    Args:
        sql: A single Standard SQL SELECT statement. Fully qualify tables as
             dataset.table (e.g. aim_raw.dod_contracts_test).

    Returns:
        dict with 'rows' (list of records), 'row_count', 'bytes_processed',
        plus 'warnings'; or 'error' when blocked/failed.
    """
    start = time.time()

    ok, msg = _rate_limiter.check()
    if not ok:
        return {"status": "error", "error": msg}

    validation = validate_query(sql, CONFIG.allowed_datasets)
    if not validation.ok:
        _audit.log("query_blocked", sql=sql, errors=validation.errors)
        return {"status": "error", "error": "Blocked by safety rules: " + " ".join(validation.errors)}

    # Dry run: free, validates syntax, estimates bytes.
    try:
        dry = _bq().query(sql, job_config=bigquery.QueryJobConfig(dry_run=True, use_legacy_sql=False))
        bytes_est = int(dry.total_bytes_processed or 0)
    except GoogleCloudError as e:
        _audit.log("query_invalid", sql=sql, error=str(e))
        return {"status": "error", "error": f"Query validation failed: {e}"}

    _rate_limiter.record()

    if CONFIG.is_dry_run:
        _audit.log("query_dry_run", sql=sql, bytes_estimate=bytes_est)
        return {
            "status": "success",
            "mode": "DRY_RUN",
            "message": f"Query is valid and would scan {_fmt_bytes(bytes_est)}. "
                       "Execution is disabled (DRY_RUN mode) - report the validated SQL to the user.",
            "bytes_estimate": bytes_est,
            "warnings": validation.warnings,
        }

    try:
        job = _bq().query(sql, job_config=bigquery.QueryJobConfig(
            use_legacy_sql=False,
            maximum_bytes_billed=CONFIG.max_bytes_billed,
        ))
        rows = [dict(r) for r in job.result(max_results=CONFIG.max_rows,
                                            timeout=CONFIG.query_timeout_s)]
        bytes_used = int(job.total_bytes_processed or bytes_est)
    except GoogleCloudError as e:
        _audit.log("query_failed", sql=sql, error=str(e),
                   duration_ms=int((time.time() - start) * 1000))
        return {"status": "error", "error": f"Query execution failed: {e}"}

    duration_ms = int((time.time() - start) * 1000)
    _audit.log("query_ok", sql=sql, bytes=bytes_used, rows=len(rows), duration_ms=duration_ms)

    return {
        "status": "success",
        "mode": "LIVE",
        "rows": [{k: (str(v) if v is not None else None) for k, v in r.items()} for r in rows],
        "row_count": len(rows),
        "row_limit": CONFIG.max_rows,
        "bytes_processed": bytes_used,
        "bytes_display": _fmt_bytes(bytes_used),
        "duration_ms": duration_ms,
        "warnings": validation.warnings,
    }
