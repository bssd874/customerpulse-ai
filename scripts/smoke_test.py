"""End-to-end local smoke test for the hackathon demo."""

from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ai import generate_next_best_action
from src.analytics import build_customer_360, customer_context
from src.config import CUSTOMER_FILES
from src.data import EXPECTED_COLUMNS, load_data


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def main() -> int:
    check(all(path.exists() for path in CUSTOMER_FILES.values()), "all data files exist")
    frames = load_data()
    check(set(frames) == set(EXPECTED_COLUMNS), "all datasets load")
    for name, expected in EXPECTED_COLUMNS.items():
        check(expected <= set(frames[name].columns), f"{name} has expected columns")

    customers = frames["customers"]
    check(customers["name"].eq("Sarah Khan").any(), "Sarah Khan exists")
    customer_360 = build_customer_360(frames)
    check(len(customer_360) == len(customers), "Customer 360 contains one row per customer")
    sarah = customer_360.loc[customer_360["name"].eq("Sarah Khan")].iloc[0]
    check(float(sarah["transaction_change_pct"]) <= -40, "Sarah has a material transaction decline")
    check(int(sarah["recent_failed_transactions"]) >= 2, "Sarah has repeated recent failures")
    check(int(sarah["unresolved_tickets"]) >= 2, "Sarah has unresolved support issues")
    check(float(sarah["sentiment_score"]) <= -0.55, "Sarah has strongly negative sentiment")
    check(sarah["risk_tier"] == "HIGH", "Sarah evaluates to HIGH risk")
    check(int(sarah["risk_score"]) == int(customer_360["risk_score"].max()), "Sarah is a top risk story")
    check(
        int(sarah["risk_score"])
        > int(customer_360.loc[customer_360["name"].ne("Sarah Khan"), "risk_score"].max()),
        "Sarah is the unique highest-risk demo story",
    )

    action = generate_next_best_action(customer_context(sarah))
    check(action["source"] == "deterministic", "fallback recommendation is explicitly labeled")
    check(bool(action["recommended_action"]), "fallback recommendation is actionable")
    logging.getLogger("streamlit.runtime.caching.cache_data_api").setLevel(logging.ERROR)
    module = importlib.import_module("app")
    check(callable(module.main), "Streamlit app imports successfully")
    print("Smoke test complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
