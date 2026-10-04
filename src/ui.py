"""Reusable Streamlit presentation helpers and controlled question routing."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd


APP_CSS = """
<style>
    .stApp { background: linear-gradient(180deg, #f7f9fc 0%, #ffffff 36%); }
    .block-container { max-width: 1240px; padding-top: 2rem; padding-bottom: 3rem; }
    .cp-hero { padding: 1.2rem 1.4rem; border-radius: 18px; color: white;
        background: linear-gradient(120deg, #10233f 0%, #155e75 60%, #0891b2 100%);
        box-shadow: 0 12px 30px rgba(15, 42, 68, .16); margin-bottom: 1rem; }
    .cp-eyebrow { color: #a5f3fc; font-weight: 700; letter-spacing: .09em; font-size: .75rem; }
    .cp-hero h1 { margin: .25rem 0 .15rem; font-size: 2.35rem; }
    .cp-hero p { color: #e0f2fe; margin: 0; font-size: 1.06rem; }
    .cp-card { border: 1px solid #dbe5ee; border-radius: 14px; padding: 1rem 1.1rem;
        background: white; box-shadow: 0 5px 16px rgba(15, 42, 68, .06); margin-bottom: .75rem; }
    .cp-label { color: #526477; text-transform: uppercase; letter-spacing: .06em;
        font-size: .7rem; font-weight: 700; }
    .cp-value { color: #10233f; font-weight: 750; font-size: 1.08rem; margin-top: .2rem; }
    .risk-high { color: #b91c1c; font-weight: 800; }
    .risk-medium { color: #b45309; font-weight: 800; }
    .risk-low { color: #047857; font-weight: 800; }
    div[data-testid="stMetric"] { background: white; border: 1px solid #dbe5ee;
        padding: .8rem 1rem; border-radius: 14px; box-shadow: 0 4px 12px rgba(15, 42, 68, .05); }
    div[data-testid="stMetricLabel"] { color: #526477; }
    .stTabs [data-baseweb="tab-list"] { gap: .35rem; }
    .stTabs [data-baseweb="tab"] { background: #edf3f8; border-radius: 10px 10px 0 0; padding: .6rem 1rem; }
</style>
"""


def money(value: Any) -> str:
    return f"${float(value):,.0f}"


def trend(value: Any) -> str:
    number = float(value)
    arrow = "▲" if number > 0 else "▼" if number < 0 else "→"
    return f"{arrow} {number:+.1f}%"


def relationship_years(customer_since: Any, as_of: Any) -> float:
    return max(0.0, (pd.Timestamp(as_of) - pd.Timestamp(customer_since)).days / 365.25)


def risk_contribution_text(explanations: Any) -> list[str]:
    if not isinstance(explanations, list):
        return []
    return [f"+{int(item['points'])}  {item['reason']}" for item in explanations]


def answer_customer_question(question: str, customer_360: pd.DataFrame) -> dict[str, Any]:
    """Route a controlled set of natural-language questions to grounded answers."""

    query = re.sub(r"\s+", " ", question.lower().strip())
    columns = ["name", "segment", "lifetime_value", "risk_score", "risk_tier"]

    named = customer_360[
        customer_360["name"].str.lower().map(lambda name: name in query or name.split()[0] in query)
    ]
    if ("why" in query or "risk" in query) and not named.empty:
        row = named.iloc[0]
        reasons = risk_contribution_text(row["risk_explanations"])
        answer = f"{row['name']} is {row['risk_tier']} risk at {int(row['risk_score'])}/100."
        if reasons:
            answer += " The score is driven by " + "; ".join(reasons) + "."
        return {"answer": answer, "table": named[columns]}

    if "unresolved" in query or "support issue" in query or "open ticket" in query:
        result = customer_360[customer_360["unresolved_tickets"] > 0].sort_values(
            ["unresolved_tickets", "risk_score"], ascending=False
        )
        return {
            "answer": f"{len(result)} customers currently have unresolved or escalated support issues.",
            "table": result[
                ["name", "unresolved_tickets", "latest_ticket_summary", "risk_score", "risk_tier"]
            ],
        }

    if "negative" in query and ("sentiment" in query or "call" in query):
        result = customer_360[customer_360["sentiment_score"] < -0.2].sort_values(
            "sentiment_score"
        )
        return {
            "answer": f"{len(result)} customers have negative latest-call sentiment.",
            "table": result[["name", "sentiment_label", "sentiment_score", "risk_score"]],
        }

    if "retention" in query or "contact first" in query or "priority" in query:
        result = customer_360.sort_values(
            ["risk_score", "lifetime_value"], ascending=[False, False]
        ).head(5)
        return {
            "answer": "This is the recommended retention queue, ordered by risk and then relationship value.",
            "table": result[columns + ["unresolved_tickets"]],
        }

    if "high-value" in query or "high value" in query or "most at risk" in query:
        cutoff = customer_360["lifetime_value"].quantile(0.75)
        result = customer_360[
            (customer_360["lifetime_value"] >= cutoff) & (customer_360["risk_tier"] != "LOW")
        ].sort_values(["risk_score", "lifetime_value"], ascending=False)
        noun = "customer is" if len(result) == 1 else "customers are"
        return {
            "answer": f"{len(result)} top-quartile-value {noun} currently at medium or high risk.",
            "table": result[columns + ["transaction_change_pct", "unresolved_tickets"]],
        }

    return {
        "answer": (
            "I can answer grounded questions about high-value risk, a named customer's risk, "
            "unresolved support issues, retention priority, or negative call sentiment."
        ),
        "table": None,
    }
