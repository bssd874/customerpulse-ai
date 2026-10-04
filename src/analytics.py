"""Deterministic Customer 360 analytics and explainable risk scoring."""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd


RECENT_DAYS = 90
NEGATIVE_TERMS = {
    "frustrated": 2,
    "unacceptable": 2,
    "disappointed": 2,
    "move to another": 3,
    "leave": 2,
    "still not": 1,
    "repeated": 1,
    "declined": 1,
    "failed": 1,
    "problem": 1,
    "issue": 1,
    "concerned": 1,
    "waiting": 1,
}
POSITIVE_TERMS = {
    "happy": 2,
    "excellent": 2,
    "resolved": 1,
    "helpful": 1,
    "satisfied": 2,
    "thank": 1,
    "works well": 2,
    "appreciate": 1,
}


def sentiment_fallback(text: str | None) -> tuple[float, str]:
    """Return a repeatable lexicon sentiment score in [-1, 1] and label."""

    normalized = (text or "").lower()
    negative = sum(weight for term, weight in NEGATIVE_TERMS.items() if term in normalized)
    positive = sum(weight for term, weight in POSITIVE_TERMS.items() if term in normalized)
    if not normalized.strip() or (negative == 0 and positive == 0):
        score = 0.0
    else:
        score = max(-1.0, min(1.0, (positive - negative) / max(4.0, negative + positive)))

    if score <= -0.55:
        label = "STRONGLY NEGATIVE"
    elif score <= -0.20:
        label = "NEGATIVE"
    elif score >= 0.45:
        label = "POSITIVE"
    else:
        label = "NEUTRAL"
    return round(score, 2), label


def risk_tier(score: int | float) -> str:
    """Map a score onto the documented risk boundaries."""

    if score >= 65:
        return "HIGH"
    if score >= 35:
        return "MEDIUM"
    return "LOW"


def score_risk(
    sentiment_score: float,
    unresolved_tickets: int,
    transaction_change_pct: float,
    recent_failed_transactions: int,
) -> dict[str, Any]:
    """Compute a capped score and retain every auditable contribution."""

    contributions: list[dict[str, Any]] = []
    if sentiment_score <= -0.55:
        contributions.append({"points": 30, "reason": "Strongly negative call sentiment"})
    elif sentiment_score <= -0.20:
        contributions.append({"points": 15, "reason": "Moderately negative call sentiment"})

    if unresolved_tickets >= 2:
        contributions.append(
            {"points": 25, "reason": f"{unresolved_tickets} unresolved support tickets"}
        )
    elif unresolved_tickets == 1:
        contributions.append({"points": 10, "reason": "1 unresolved support ticket"})

    if transaction_change_pct <= -40:
        contributions.append(
            {"points": 25, "reason": f"Transaction value declined {abs(transaction_change_pct):.0f}%"}
        )
    elif transaction_change_pct <= -20:
        contributions.append(
            {"points": 15, "reason": f"Transaction value declined {abs(transaction_change_pct):.0f}%"}
        )

    if recent_failed_transactions >= 2:
        contributions.append(
            {"points": 20, "reason": f"{recent_failed_transactions} recent failed transactions"}
        )
    elif recent_failed_transactions == 1:
        contributions.append({"points": 10, "reason": "1 recent failed transaction"})

    score = min(100, sum(item["points"] for item in contributions))
    return {
        "risk_score": score,
        "risk_tier": risk_tier(score),
        "risk_explanations": contributions,
    }


def calculate_transaction_metrics(
    transactions: pd.DataFrame, analysis_date: pd.Timestamp | str | None = None
) -> pd.DataFrame:
    """Aggregate all-time counts and comparable 90-day value windows."""

    tx = transactions.copy()
    tx["transaction_date"] = pd.to_datetime(tx["transaction_date"])
    anchor = pd.Timestamp(analysis_date) if analysis_date is not None else tx["transaction_date"].max()
    recent_start = anchor - pd.offsets.Day(RECENT_DAYS - 1)
    previous_start = recent_start - pd.offsets.Day(RECENT_DAYS)

    tx["is_success"] = tx["status"].eq("SUCCESS")
    tx["is_failed"] = tx["status"].isin(["FAILED", "DECLINED"])
    tx["is_recent"] = tx["transaction_date"].between(recent_start, anchor)
    tx["is_previous"] = tx["transaction_date"].between(
        previous_start, recent_start - pd.offsets.Day(1)
    )
    tx["recent_value"] = tx["amount"].where(tx["is_recent"] & tx["is_success"], 0.0)
    tx["previous_value"] = tx["amount"].where(tx["is_previous"] & tx["is_success"], 0.0)
    tx["recent_failure"] = (tx["is_recent"] & tx["is_failed"]).astype(int)

    metrics = (
        tx.groupby("customer_id", as_index=False)
        .agg(
            total_transactions=("transaction_id", "count"),
            successful_transactions=("is_success", "sum"),
            failed_transactions=("is_failed", "sum"),
            recent_failed_transactions=("recent_failure", "sum"),
            recent_transaction_value=("recent_value", "sum"),
            previous_transaction_value=("previous_value", "sum"),
        )
    )
    previous = metrics["previous_transaction_value"]
    recent = metrics["recent_transaction_value"]
    metrics["transaction_change_pct"] = 0.0
    has_previous = previous.gt(0)
    metrics.loc[has_previous, "transaction_change_pct"] = (
        (recent[has_previous] - previous[has_previous]) / previous[has_previous] * 100
    )
    metrics.loc[~has_previous & recent.gt(0), "transaction_change_pct"] = 100.0
    metrics["transaction_change_pct"] = metrics["transaction_change_pct"].round(1)
    return metrics


def _latest_by_customer(frame: pd.DataFrame, date_column: str) -> pd.DataFrame:
    return frame.sort_values(date_column).drop_duplicates("customer_id", keep="last")


def build_customer_360(
    frames: Mapping[str, pd.DataFrame], analysis_date: pd.Timestamp | str | None = None
) -> pd.DataFrame:
    """Combine the four datasets into one explainable Customer 360 table."""

    customers = frames["customers"].copy()
    transactions = frames["transactions"].copy()
    tickets = frames["support_tickets"].copy()
    calls = frames["call_transcripts"].copy()

    tx_metrics = calculate_transaction_metrics(transactions, analysis_date)
    ticket_metrics = (
        tickets.assign(unresolved=tickets["status"].isin(["OPEN", "ESCALATED"]))
        .groupby("customer_id", as_index=False)
        .agg(total_tickets=("ticket_id", "count"), unresolved_tickets=("unresolved", "sum"))
    )
    latest_tickets = _latest_by_customer(tickets, "created_at")[["customer_id", "summary"]].rename(
        columns={"summary": "latest_ticket_summary"}
    )
    latest_calls = _latest_by_customer(calls, "call_date")[["customer_id", "transcript"]].rename(
        columns={"transcript": "latest_call_transcript"}
    )

    result = customers.merge(tx_metrics, on="customer_id", how="left")
    result = result.merge(ticket_metrics, on="customer_id", how="left")
    result = result.merge(latest_tickets, on="customer_id", how="left")
    result = result.merge(latest_calls, on="customer_id", how="left")

    numeric_defaults = [
        "total_transactions",
        "successful_transactions",
        "failed_transactions",
        "recent_failed_transactions",
        "recent_transaction_value",
        "previous_transaction_value",
        "transaction_change_pct",
        "total_tickets",
        "unresolved_tickets",
    ]
    result[numeric_defaults] = result[numeric_defaults].fillna(0)
    result["latest_ticket_summary"] = result["latest_ticket_summary"].fillna("No support tickets")
    result["latest_call_transcript"] = result["latest_call_transcript"].fillna(
        "No call transcript available"
    )

    sentiments = result["latest_call_transcript"].map(sentiment_fallback)
    result["sentiment_score"] = sentiments.map(lambda item: item[0])
    result["sentiment_label"] = sentiments.map(lambda item: item[1])

    scores = result.apply(
        lambda row: score_risk(
            float(row["sentiment_score"]),
            int(row["unresolved_tickets"]),
            float(row["transaction_change_pct"]),
            int(row["recent_failed_transactions"]),
        ),
        axis=1,
    )
    result["risk_score"] = scores.map(lambda item: item["risk_score"])
    result["risk_tier"] = scores.map(lambda item: item["risk_tier"])
    result["risk_explanations"] = scores.map(lambda item: item["risk_explanations"])

    integer_columns = [
        "total_transactions",
        "successful_transactions",
        "failed_transactions",
        "recent_failed_transactions",
        "total_tickets",
        "unresolved_tickets",
        "risk_score",
    ]
    result[integer_columns] = result[integer_columns].astype(int)
    return result.sort_values(["risk_score", "lifetime_value"], ascending=[False, False]).reset_index(
        drop=True
    )


def customer_context(row: pd.Series | Mapping[str, Any]) -> dict[str, Any]:
    """Create a serializable, evidence-only context for the recommendation layer."""

    values = row.to_dict() if isinstance(row, pd.Series) else dict(row)
    keep = (
        "customer_id",
        "name",
        "segment",
        "region",
        "product",
        "lifetime_value",
        "recent_transaction_value",
        "previous_transaction_value",
        "transaction_change_pct",
        "recent_failed_transactions",
        "unresolved_tickets",
        "latest_ticket_summary",
        "latest_call_transcript",
        "sentiment_score",
        "sentiment_label",
        "risk_score",
        "risk_tier",
        "risk_explanations",
    )
    return {key: values.get(key) for key in keep}
