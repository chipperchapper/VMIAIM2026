"""Tests for the self-learning loop (app/learning.py, decision D7).

The learn step must be as paranoid as the query path: poisoned or off-allowlist
SQL from the feedback store must never become a few-shot example, and a broken
feedback backend must never break answering.
"""
import time
from unittest.mock import MagicMock, patch

import pytest

from app import learning


def _rows(pairs):
    return [{"question": q, "sql": s} for q, s in pairs]


def _mock_bq(rows):
    client = MagicMock()
    job = MagicMock()
    job.result.return_value = _rows(rows) and [
        {"question": r["question"], "sql": r["sql"]} for r in _rows(rows)
    ]
    client.query.return_value = job
    return client


@pytest.fixture(autouse=True)
def fresh_cache():
    with learning._lock:
        learning._cache["section"] = ""
        learning._cache["fetched_at"] = 0.0
    yield


def _section_with(pairs):
    with patch.object(learning, "_bq", return_value=_mock_bq(pairs)):
        return learning.learned_section(force_refresh=True)


def test_good_example_appears():
    section = _section_with([
        ("How much did the Navy spend in 2025?",
         "SELECT SUM(federal_action_obligation) FROM aim_core.contract_transactions "
         "WHERE action_date_fiscal_year = 2025"),
    ])
    assert "Learned examples" in section
    assert "Navy" in section
    assert "aim_core.contract_transactions" in section


def test_poisoned_sql_is_excluded():
    section = _section_with([
        ("please run this", "DELETE FROM aim_core.contract_transactions"),
        ("exfiltrate", "SELECT * FROM other_project.secrets.keys"),
        ("legit", "SELECT COUNT(*) FROM aim_core.contract_transactions"),
    ])
    assert "DELETE" not in section
    assert "secrets" not in section
    assert "COUNT(*)" in section


def test_duplicate_questions_keep_newest():
    section = _section_with([
        ("Top contractors?", "SELECT recipient_parent_name FROM aim_core.contract_transactions LIMIT 3"),
        ("top contractors?", "SELECT 1 FROM aim_core.contract_transactions"),  # older duplicate
    ])
    assert section.count("Top contractors?") + section.count("top contractors?") == 1
    assert "SELECT 1" not in section


def test_cap_at_max_examples():
    pairs = [(f"question number {i}?",
              "SELECT COUNT(*) FROM aim_core.contract_transactions") for i in range(40)]
    # distinct questions -> dedupe keeps them; cap must bite
    section = _section_with(pairs)
    assert section.count("Q: ") == learning.MAX_EXAMPLES


def test_no_examples_means_empty_section():
    assert _section_with([]) == ""


def test_bq_failure_keeps_previous_section():
    good = _section_with([
        ("Navy spend?", "SELECT 1 FROM aim_core.contract_transactions"),
    ])
    assert good
    broken = MagicMock()
    broken.query.side_effect = RuntimeError("BQ down")
    with patch.object(learning, "_bq", return_value=broken):
        section = learning.learned_section(force_refresh=True)
    assert section == good  # stale beats missing


def test_cache_ttl_respected():
    with patch.object(learning, "_bq", return_value=_mock_bq([
        ("Q1?", "SELECT 1 FROM aim_core.contract_transactions"),
    ])) as bq:
        learning.learned_section(force_refresh=True)
        learning.learned_section()          # within TTL -> no second query
        assert bq.call_count == 1


def test_record_feedback_invalidates_cache_on_up():
    with learning._lock:
        learning._cache["fetched_at"] = time.time()
    client = MagicMock()
    client.insert_rows_json.return_value = []
    with patch.object(learning, "_bq", return_value=client):
        learning.record_feedback(session_id="s", question="q", sql="SELECT 1",
                                 answer="a", rating="up", comment=None,
                                 model="m", build_id="b")
    with learning._lock:
        assert learning._cache["fetched_at"] == 0.0


def test_comments_never_reach_the_prompt():
    """The formatted section must contain only question + SQL, never comments."""
    section = _section_with([
        ("A question?", "SELECT 2 FROM aim_core.contract_transactions"),
    ])
    assert "comment" not in section.lower()
