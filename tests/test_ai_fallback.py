from __future__ import annotations

from src.ai import explain_risk, generate_next_best_action


SARAH_CONTEXT = {
    "name": "Sarah Khan",
    "risk_tier": "HIGH",
    "risk_score": 100,
    "unresolved_tickets": 3,
    "recent_failed_transactions": 2,
    "transaction_change_pct": -58.1,
    "latest_ticket_summary": "Second overseas transaction declined after repeated support contact.",
    "risk_explanations": [
        {"points": 30, "reason": "Strongly negative call sentiment"},
        {"points": 25, "reason": "3 unresolved support tickets"},
        {"points": 25, "reason": "Transaction value declined 58%"},
        {"points": 20, "reason": "2 recent failed transactions"},
    ],
}


def test_risk_explanation_fallback_is_grounded_and_labeled() -> None:
    result = explain_risk(SARAH_CONTEXT)
    assert result["source"] == "deterministic"
    assert "Sarah Khan" in result["text"]
    assert "100/100" in result["text"]
    assert "Strongly negative" in result["text"]


def test_next_best_action_fallback_is_complete() -> None:
    result = generate_next_best_action(SARAH_CONTEXT)
    assert result["source"] == "deterministic"
    assert result["priority"].startswith("P1")
    for key in (
        "priority",
        "recommended_action",
        "why",
        "suggested_outreach",
        "business_objective",
    ):
        assert result[key]
    assert "Sarah Khan" in result["suggested_outreach"]

