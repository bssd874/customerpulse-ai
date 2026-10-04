from __future__ import annotations

from src.data import EXPECTED_COLUMNS, load_data, validate_data


def test_generated_data_integrity() -> None:
    frames = load_data()
    validation = validate_data(frames)
    assert validation.valid, validation.errors
    assert 12 <= len(frames["customers"]) <= 15
    assert 80 <= len(frames["transactions"]) <= 120
    assert 25 <= len(frames["support_tickets"]) <= 35
    assert 15 <= len(frames["call_transcripts"]) <= 20
    for name, expected in EXPECTED_COLUMNS.items():
        assert expected == set(frames[name].columns)


def test_required_status_variety_is_present() -> None:
    frames = load_data()
    assert {"SUCCESS", "FAILED", "DECLINED"} <= set(frames["transactions"]["status"])
    assert {"OPEN", "RESOLVED", "ESCALATED"} <= set(frames["support_tickets"]["status"])


def test_all_activity_references_a_customer() -> None:
    frames = load_data()
    customer_ids = set(frames["customers"]["customer_id"])
    for name in ("transactions", "support_tickets", "call_transcripts"):
        assert set(frames[name]["customer_id"]) <= customer_ids

