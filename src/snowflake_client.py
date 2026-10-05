"""Optional Snowflake connectivity with safe Streamlit Cloud support.

Every remote capability is optional. A failed connection, stale session,
unavailable model, or missing Cortex privilege returns the app to its
deterministic path instead of crashing the UI.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from src.config import DEFAULT_DATABASE, DEFAULT_SCHEMA, env

try:
    import snowflake.connector as sf_connector
except ImportError:  # The complete local demo works without the optional connector.
    sf_connector = None  # type: ignore[assignment]


AI_MODEL_CANDIDATES = (
    "claude-sonnet-4-5",
    "llama3.3-70b",
    "llama3.1-8b",
    "mistral-large2",
)
SENTIMENT_LABELS = {"positive", "negative", "neutral", "mixed", "unknown"}
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SnowflakeSettings:
    """Resolved connection settings without a printable secret representation."""

    values: dict[str, Any]
    source: str

    @property
    def configured(self) -> bool:
        return bool(
            self.values.get("connection_name")
            or (self.values.get("account") and self.values.get("user"))
            or self.source == "local_profile"
        )


def _clean_value(value: Any) -> Any | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value or value.upper().startswith("YOUR_"):
            return None
    return value


def _safe_section(secrets: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if secrets is None:
        return {}
    try:
        section = secrets.get("snowflake", {})
        return section if isinstance(section, Mapping) else dict(section)
    except (KeyError, TypeError, ValueError):
        return {}


def load_snowflake_settings(
    secrets: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
    local_profile_available: bool = False,
) -> SnowflakeSettings:
    """Resolve Streamlit secrets, environment variables, then a local profile."""

    supported = {
        "account",
        "user",
        "password",
        "warehouse",
        "database",
        "schema",
        "role",
        "authenticator",
        "token",
        "private_key_file",
        "private_key_file_pwd",
        "connection_name",
    }
    secret_values = {
        key: _clean_value(value)
        for key, value in _safe_section(secrets).items()
        if key in supported
    }
    secret_values = {key: value for key, value in secret_values.items() if value is not None}
    if secret_values.get("account") and secret_values.get("user"):
        secret_values.setdefault("database", DEFAULT_DATABASE)
        secret_values.setdefault("schema", DEFAULT_SCHEMA)
        return SnowflakeSettings(secret_values, "streamlit_secrets")

    source_env = environ if environ is not None else os.environ
    env_names = {
        "account": "SNOWFLAKE_ACCOUNT",
        "user": "SNOWFLAKE_USER",
        "password": "SNOWFLAKE_PASSWORD",
        "warehouse": "SNOWFLAKE_WAREHOUSE",
        "database": "SNOWFLAKE_DATABASE",
        "schema": "SNOWFLAKE_SCHEMA",
        "role": "SNOWFLAKE_ROLE",
        "authenticator": "SNOWFLAKE_AUTHENTICATOR",
        "token": "SNOWFLAKE_TOKEN",
        "private_key_file": "SNOWFLAKE_PRIVATE_KEY_FILE",
        "private_key_file_pwd": "SNOWFLAKE_PRIVATE_KEY_FILE_PWD",
        "connection_name": "SNOWFLAKE_CONNECTION_NAME",
    }
    env_values = {
        key: _clean_value(source_env.get(name)) for key, name in env_names.items()
    }
    env_values = {key: value for key, value in env_values.items() if value is not None}
    if env_values.get("connection_name") or (
        env_values.get("account") and env_values.get("user")
    ):
        env_values.setdefault("database", DEFAULT_DATABASE)
        env_values.setdefault("schema", DEFAULT_SCHEMA)
        return SnowflakeSettings(env_values, "environment")

    if local_profile_available:
        return SnowflakeSettings({}, "local_profile")
    return SnowflakeSettings({}, "none")


def parse_ai_sentiment_response(result: Any) -> str:
    """Extract Snowflake's truthful overall label from an AI_SENTIMENT object."""

    if result is None:
        raise ValueError("AI_SENTIMENT returned no result")
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError as exc:
            raise ValueError("AI_SENTIMENT returned invalid JSON") from exc
    if not isinstance(result, Mapping):
        raise ValueError("AI_SENTIMENT returned an unexpected value")
    categories = result.get("categories")
    if not isinstance(categories, list):
        raise ValueError("AI_SENTIMENT response has no categories")
    for item in categories:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("name", "")).lower() != "overall":
            continue
        label = str(item.get("sentiment", "unknown")).lower()
        return (label if label in SENTIMENT_LABELS else "unknown").upper()
    raise ValueError("AI_SENTIMENT response has no overall sentiment")


class SnowflakeClient:
    """Connect, validate, query, and gracefully recover from stale sessions."""

    def __init__(self, secrets: Mapping[str, Any] | None = None) -> None:
        self.connection: Any | None = None
        self.diagnostic = "Snowflake connection not attempted"
        self.ai_diagnostic = "Snowflake AI not tested"
        self.health: dict[str, Any] = {}
        self.sentiment_available: bool | None = None
        self.ai_complete_available: bool | None = None
        self.working_ai_model: str | None = None
        self.settings = load_snowflake_settings(
            secrets,
            local_profile_available=any(path.exists() for path in self._config_candidates()),
        )

    @staticmethod
    def _config_candidates() -> list[Path]:
        user = Path.home()
        custom_home = os.getenv("SNOWFLAKE_HOME")
        paths = [
            user / ".snowflake" / "connections.toml",
            user / ".snowflake" / "config.toml",
            user / "AppData" / "Local" / "snowflake" / "connections.toml",
            user / "AppData" / "Local" / "snowflake" / "config.toml",
        ]
        if custom_home:
            paths[:0] = [
                Path(custom_home) / "connections.toml",
                Path(custom_home) / "config.toml",
            ]
        return paths

    def has_connection_hint(self) -> bool:
        return self.settings.configured

    @property
    def connected(self) -> bool:
        return self.connection is not None

    @property
    def ai_active(self) -> bool:
        return bool(self.sentiment_available and self.ai_complete_available)

    @property
    def database(self) -> str:
        return str(self.settings.values.get("database", DEFAULT_DATABASE))

    @property
    def schema(self) -> str:
        return str(self.settings.values.get("schema", DEFAULT_SCHEMA))

    @staticmethod
    def _identifier(value: str) -> str:
        return '"' + value.replace('"', '""') + '"'

    @staticmethod
    def _sanitized_error(feature: str, exc: Exception) -> str:
        message = str(exc).upper()
        if "CORTEX_USER" in message or "USE AI FUNCTIONS" in message:
            return f"{feature} unavailable: required Cortex AI role/privilege is missing"
        if "MODEL" in message and ("NOT" in message or "UNAVAILABLE" in message):
            return f"{feature} unavailable: no probed model is enabled in this account/region"
        return f"{feature} unavailable ({type(exc).__name__})"

    def connect(self) -> bool:
        """Connect and require a successful non-sensitive health check."""

        if self.connected:
            return True
        if sf_connector is None:
            self.diagnostic = "Snowflake connector is not installed"
            LOGGER.info(self.diagnostic)
            return False
        if not self.has_connection_hint():
            self.diagnostic = "No Snowflake configuration detected"
            LOGGER.info(self.diagnostic)
            return False

        try:
            kwargs = dict(self.settings.values)
            kwargs.update(login_timeout=8, network_timeout=15, socket_timeout=15)
            self.connection = sf_connector.connect(**kwargs)
            self.health_check()
            self.diagnostic = "Live Snowflake health check passed"
            LOGGER.info(self.diagnostic)
            return True
        except Exception as exc:  # Connector exceptions differ by auth method/version.
            self._discard_connection()
            self.diagnostic = self._sanitized_error("Snowflake connection", exc)
            LOGGER.info(self.diagnostic)
            return False

    def _discard_connection(self) -> None:
        connection, self.connection = self.connection, None
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass

    def close(self) -> None:
        self._discard_connection()

    def ensure_connection(self) -> bool:
        """Validate a cached session, reconnecting once when it became stale."""

        if not self.connected:
            return self.connect()
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return True
        except Exception:
            self._discard_connection()
            return self.connect()

    def health_check(self) -> dict[str, Any]:
        if not self.connected:
            raise RuntimeError("Snowflake is not connected")
        sql = (
            "SELECT CURRENT_ACCOUNT(), CURRENT_USER(), CURRENT_ROLE(), CURRENT_WAREHOUSE(), "
            "CURRENT_DATABASE(), CURRENT_SCHEMA()"
        )
        with self.connection.cursor() as cursor:
            cursor.execute(sql)
            row = cursor.fetchone()
        keys = ("account", "user", "role", "warehouse", "database", "schema")
        self.health = dict(zip(keys, row or (None,) * len(keys), strict=False))
        return dict(self.health)

    def execute_scalar(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        if not self.ensure_connection():
            raise RuntimeError("Snowflake is not connected")
        with self.connection.cursor() as cursor:
            cursor.execute(sql, params)
            row = cursor.fetchone()
        return row[0] if row else None

    def fetch_customer_360(self) -> pd.DataFrame:
        """Fetch the live project view; callers decide whether to use local fallback."""

        if not self.ensure_connection():
            raise RuntimeError("Snowflake is not connected")
        qualified = ".".join(
            self._identifier(value) for value in (self.database, self.schema, "CUSTOMER_360")
        )
        with self.connection.cursor() as cursor:
            cursor.execute(f"SELECT * FROM {qualified}")
            rows = cursor.fetchall()
            columns = [column[0].lower() for column in cursor.description]
        return pd.DataFrame(rows, columns=columns)

    def probe_ai_sentiment(self) -> bool:
        if self.sentiment_available is not None:
            return self.sentiment_available
        try:
            self.ai_sentiment("The service was helpful.", _skip_probe=True)
            self.sentiment_available = True
        except Exception as exc:
            self.sentiment_available = False
            self.ai_diagnostic = self._sanitized_error("AI_SENTIMENT", exc)
        return self.sentiment_available

    def probe_ai_complete(self) -> bool:
        if self.ai_complete_available is not None:
            return self.ai_complete_available
        configured = env("SNOWFLAKE_AI_MODEL")
        candidates = tuple(
            dict.fromkeys([candidate for candidate in (configured, *AI_MODEL_CANDIDATES) if candidate])
        )
        last_error: Exception | None = None
        for model in candidates:
            try:
                result = self.execute_scalar(
                    "SELECT AI_COMPLETE(%s, %s, {'temperature': 0, 'max_tokens': 8})",
                    (model, "Reply with exactly OK."),
                )
                if result:
                    self.working_ai_model = model
                    self.ai_complete_available = True
                    self.ai_diagnostic = f"Snowflake AI verified with {model}"
                    return True
            except Exception as exc:
                last_error = exc
                message = str(exc).upper()
                if any(
                    marker in message
                    for marker in ("CORTEX_USER", "USE AI FUNCTIONS", "INSUFFICIENT PRIVILEGES")
                ):
                    break
        self.ai_complete_available = False
        self.ai_diagnostic = self._sanitized_error(
            "AI_COMPLETE", last_error or RuntimeError("No model candidates")
        )
        LOGGER.info(self.ai_diagnostic)
        return False

    def probe_ai_capabilities(self) -> bool:
        if not self.connected:
            return False
        sentiment = self.probe_ai_sentiment()
        completion = self.probe_ai_complete()
        if sentiment and completion:
            self.ai_diagnostic = f"Snowflake AI verified with {self.working_ai_model}"
        return sentiment and completion

    def ai_complete(self, prompt: str) -> str:
        """Generate with the first account-verified AI_COMPLETE model."""

        if not self.probe_ai_complete() or not self.working_ai_model:
            raise RuntimeError(self.ai_diagnostic)
        result = self.execute_scalar(
            "SELECT AI_COMPLETE(%s, %s, {'temperature': 0, 'max_tokens': 350})",
            (self.working_ai_model, prompt),
        )
        if result is None:
            raise RuntimeError("AI_COMPLETE returned no result")
        return str(result)

    def ai_sentiment(self, text: str, _skip_probe: bool = False) -> str:
        """Return only Snowflake's native overall sentiment classification."""

        if not _skip_probe and not self.probe_ai_sentiment():
            raise RuntimeError(self.ai_diagnostic)
        result = self.execute_scalar("SELECT AI_SENTIMENT(%s)", (text,))
        return parse_ai_sentiment_response(result)

    def enrich_customer_sentiments(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Run AI_SENTIMENT in one Snowflake query without changing risk scores."""

        if not self.probe_ai_sentiment():
            raise RuntimeError(self.ai_diagnostic)
        qualified = ".".join(
            self._identifier(value) for value in (self.database, self.schema, "CUSTOMER_360")
        )
        sql = (
            f"SELECT customer_id, AI_SENTIMENT(latest_call_transcript) AS sentiment_result "
            f"FROM {qualified}"
        )
        with self.connection.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()
        labels = {
            str(customer_id): parse_ai_sentiment_response(result)
            for customer_id, result in rows
            if result is not None
        }
        enriched = frame.copy()
        enriched["snowflake_sentiment_label"] = enriched["customer_id"].astype(str).map(labels)
        enriched["sentiment_source"] = enriched["snowflake_sentiment_label"].map(
            lambda value: "snowflake_ai_sentiment" if pd.notna(value) else "deterministic"
        )
        return enriched
