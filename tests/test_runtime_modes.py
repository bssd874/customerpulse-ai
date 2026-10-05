from __future__ import annotations

import pandas as pd

from app import resolve_customer_360
from src.analytics import build_customer_360
from src.data import load_data


class UnavailableCustomer360Client:
    connected = True

    def fetch_customer_360(self) -> pd.DataFrame:
        raise RuntimeError("warehouse unavailable")


class LiveCustomer360Client:
    connected = True

    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame

    def fetch_customer_360(self) -> pd.DataFrame:
        return self.frame.copy()

    def enrich_customer_sentiments(self, frame: pd.DataFrame) -> pd.DataFrame:
        result = frame.copy()
        result["snowflake_sentiment_label"] = "NEUTRAL"
        result["sentiment_source"] = "snowflake_ai_sentiment"
        return result


def test_failed_customer_360_query_returns_local_fallback() -> None:
    local = build_customer_360(load_data())
    result, source = resolve_customer_360(local, UnavailableCustomer360Client())
    assert source == "local"
    assert result["data_source"].eq("local").all()
    assert result.loc[result["name"].eq("Sarah Khan"), "risk_tier"].item() == "HIGH"


def test_successful_customer_360_query_is_explicitly_live() -> None:
    local = build_customer_360(load_data())
    result, source = resolve_customer_360(local, LiveCustomer360Client(local))
    assert source == "snowflake"
    assert result["data_source"].eq("snowflake").all()
    assert result["sentiment_source"].eq("snowflake_ai_sentiment").all()


def test_ai_sentiment_label_cannot_change_authoritative_risk_score() -> None:
    local = build_customer_360(load_data())
    result, _ = resolve_customer_360(local, LiveCustomer360Client(local))
    local_sarah = local.loc[local["name"].eq("Sarah Khan")].iloc[0]
    live_sarah = result.loc[result["name"].eq("Sarah Khan")].iloc[0]
    assert live_sarah["snowflake_sentiment_label"] == "NEUTRAL"
    assert live_sarah["risk_score"] == local_sarah["risk_score"] == 100
    assert live_sarah["risk_tier"] == local_sarah["risk_tier"] == "HIGH"
