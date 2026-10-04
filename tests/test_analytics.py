from __future__ import annotations

import pandas as pd
import pytest

from src.analytics import (
    build_customer_360,
    calculate_transaction_metrics,
    risk_tier,
    score_risk,
)
from src.data import load_data


def test_risk_score_full_signal_stack_caps_at_100() -> None:
    result = score_risk(-0.8, 3, -55.0, 2)
    assert result["risk_score"] == 100
    assert result["risk_tier"] == "HIGH"
    assert [item["points"] for item in result["risk_explanations"]] == [30, 25, 25, 20]


@pytest.mark.parametrize(
    ("score", "expected"),
    [(0, "LOW"), (34, "LOW"), (35, "MEDIUM"), (64, "MEDIUM"), (65, "HIGH"), (100, "HIGH")],
)
def test_risk_tier_boundaries(score: int, expected: str) -> None:
    assert risk_tier(score) == expected


def test_transaction_trend_uses_comparable_90_day_windows() -> None:
    transactions = pd.DataFrame(
        [
            ("T1", "C1", "2026-05-20", 600.0, "SUCCESS"),
            ("T2", "C1", "2026-06-20", 400.0, "SUCCESS"),
            ("T3", "C1", "2026-08-01", 300.0, "SUCCESS"),
            ("T4", "C1", "2026-09-01", 200.0, "SUCCESS"),
            ("T5", "C1", "2026-09-20", 100.0, "FAILED"),
        ],
        columns=["transaction_id", "customer_id", "transaction_date", "amount", "status"],
    )
    result = calculate_transaction_metrics(transactions, "2026-09-30").iloc[0]
    assert result["previous_transaction_value"] == 1000.0
    assert result["recent_transaction_value"] == 500.0
    assert result["transaction_change_pct"] == -50.0
    assert result["recent_failed_transactions"] == 1


def test_customer_360_aggregation_has_one_row_per_customer() -> None:
    frames = load_data()
    result = build_customer_360(frames)
    assert len(result) == len(frames["customers"])
    assert result["customer_id"].is_unique
    assert result["total_transactions"].sum() == len(frames["transactions"])
    assert result["total_tickets"].sum() == len(frames["support_tickets"])


def test_sarah_is_high_value_high_risk() -> None:
    result = build_customer_360(load_data())
    sarah = result.loc[result["name"].eq("Sarah Khan")].iloc[0]
    assert sarah["segment"] == "PREMIUM"
    assert sarah["lifetime_value"] >= result["lifetime_value"].quantile(0.75)
    assert sarah["transaction_change_pct"] <= -40
    assert sarah["recent_failed_transactions"] >= 2
    assert sarah["unresolved_tickets"] >= 2
    assert sarah["sentiment_label"] == "STRONGLY NEGATIVE"
    assert sarah["risk_score"] == 100
    assert sarah["risk_tier"] == "HIGH"
    assert (result.loc[result["name"].ne("Sarah Khan"), "risk_score"] < sarah["risk_score"]).all()
