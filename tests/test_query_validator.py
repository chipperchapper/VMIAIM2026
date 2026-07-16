"""Guardrail tests (proposal §6: 100% of write attempts must be blocked)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.query_validator import validate_query  # noqa: E402

ALLOWED = ("aim_raw", "aim_core", "aim_analytics")


def test_simple_select_passes():
    r = validate_query("SELECT action_date FROM aim_raw.dod_contracts_test LIMIT 10", ALLOWED)
    assert r.ok


def test_cte_passes():
    r = validate_query(
        "WITH t AS (SELECT recipient_parent_name n, federal_action_obligation d "
        "FROM aim_raw.dod_contracts_test) SELECT n, SUM(d) FROM t GROUP BY n", ALLOWED)
    assert r.ok


def test_insert_blocked():
    r = validate_query("INSERT INTO aim_raw.x VALUES (1)", ALLOWED)
    assert not r.ok


def test_delete_blocked():
    r = validate_query("DELETE FROM aim_raw.dod_contracts_test WHERE 1=1", ALLOWED)
    assert not r.ok


def test_drop_blocked():
    r = validate_query("DROP TABLE aim_raw.dod_contracts_test", ALLOWED)
    assert not r.ok


def test_multi_statement_blocked():
    r = validate_query(
        "SELECT 1 FROM aim_raw.t; DROP TABLE aim_raw.t", ALLOWED)
    assert not r.ok


def test_sneaky_keyword_in_string_allowed():
    # the word DELETE inside a string literal must not trip the guard
    r = validate_query(
        "SELECT * FROM aim_raw.dod_contracts_test "
        "WHERE transaction_description = 'DELETE old files'", ALLOWED)
    assert r.ok


def test_unapproved_dataset_blocked():
    r = validate_query("SELECT * FROM other_dataset.secrets", ALLOWED)
    assert not r.ok


def test_unapproved_project_dataset_blocked():
    r = validate_query("SELECT * FROM `some-project.hidden.t`", ALLOWED)
    assert not r.ok


def test_select_star_warns():
    r = validate_query("SELECT * FROM aim_raw.dod_contracts_test", ALLOWED)
    assert r.ok and r.warnings
