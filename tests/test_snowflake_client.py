from __future__ import annotations

import json

import pytest

from src.snowflake_client import (
    SnowflakeClient,
    load_snowflake_settings,
    parse_ai_sentiment_response,
)


def test_streamlit_secrets_take_priority_over_environment() -> None:
    settings = load_snowflake_settings(
        {
            "snowflake": {
                "account": "cloud-account",
                "user": "cloud-user",
                "password": "cloud-password",
                "warehouse": "cloud-wh",
            }
        },
        environ={"SNOWFLAKE_ACCOUNT": "environment-account", "SNOWFLAKE_USER": "env-user"},
    )
    assert settings.source == "streamlit_secrets"
    assert settings.values["account"] == "cloud-account"
    assert settings.values["database"] == "CUSTOMERPULSE_DB"
    assert settings.values["schema"] == "APP"


def test_environment_and_key_pair_configuration_are_supported() -> None:
    settings = load_snowflake_settings(
        environ={
            "SNOWFLAKE_ACCOUNT": "account",
            "SNOWFLAKE_USER": "service-user",
            "SNOWFLAKE_AUTHENTICATOR": "SNOWFLAKE_JWT",
            "SNOWFLAKE_PRIVATE_KEY_FILE": "/secure/key.p8",
        }
    )
    assert settings.source == "environment"
    assert settings.values["authenticator"] == "SNOWFLAKE_JWT"
    assert settings.values["private_key_file"] == "/secure/key.p8"


def test_placeholder_secrets_do_not_trigger_a_connection() -> None:
    settings = load_snowflake_settings(
        {"snowflake": {"account": "YOUR_ACCOUNT_IDENTIFIER", "user": "YOUR_USER"}},
        environ={},
    )
    assert settings.source == "none"
    assert not settings.configured


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({"categories": [{"name": "overall", "sentiment": "negative"}]}, "NEGATIVE"),
        (
            json.dumps({"categories": [{"name": "overall", "sentiment": "mixed"}]}),
            "MIXED",
        ),
        ({"categories": [{"name": "OVERALL", "sentiment": "new-label"}]}, "UNKNOWN"),
    ],
)
def test_ai_sentiment_response_parser(value: object, expected: str) -> None:
    assert parse_ai_sentiment_response(value) == expected


def test_ai_complete_model_probe_stops_on_first_working_model(monkeypatch: pytest.MonkeyPatch) -> None:
    client = SnowflakeClient()
    client.connection = object()
    attempted: list[str] = []

    def fake_execute(_sql: str, params: tuple[object, ...] = ()) -> str:
        model = str(params[0])
        attempted.append(model)
        if model != "llama3.1-8b":
            raise RuntimeError("model unavailable")
        return "OK"

    monkeypatch.setattr(client, "execute_scalar", fake_execute)
    assert client.probe_ai_complete()
    assert client.working_ai_model == "llama3.1-8b"
    assert attempted[-1] == "llama3.1-8b"
    assert "mistral-large2" not in attempted
