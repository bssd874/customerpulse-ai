"""Safe, optional Snowflake connectivity and AI SQL execution."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import DEFAULT_AI_MODEL, env, snowflake_namespace

try:
    import snowflake.connector
except ImportError:  # Local demo remains usable before optional dependency installation.
    snowflake = None  # type: ignore[assignment]


class SnowflakeClient:
    """Lazily connect using standard config first, then environment variables."""

    def __init__(self) -> None:
        self.connection: Any | None = None
        self.diagnostic = "Snowflake connection not attempted"
        self.ai_model = env("SNOWFLAKE_AI_MODEL", DEFAULT_AI_MODEL) or DEFAULT_AI_MODEL

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
            paths.insert(0, Path(custom_home) / "connections.toml")
            paths.insert(1, Path(custom_home) / "config.toml")
        return paths

    @classmethod
    def has_connection_hint(cls) -> bool:
        """Avoid network or login prompts when no connection source exists."""

        if any(path.exists() for path in cls._config_candidates()):
            return True
        return bool(os.getenv("SNOWFLAKE_CONNECTION_NAME")) or all(
            os.getenv(name) for name in ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER")
        )

    @property
    def connected(self) -> bool:
        return self.connection is not None

    def connect(self) -> bool:
        """Connect without exposing credentials; failure is a normal demo-mode state."""

        if self.connected:
            return True
        if snowflake is None:
            self.diagnostic = "Snowflake connector is not installed"
            return False
        if not self.has_connection_hint():
            self.diagnostic = "No Snowflake connection configuration was detected"
            return False

        try:
            connection_name = env("SNOWFLAKE_CONNECTION_NAME")
            if connection_name or any(path.exists() for path in self._config_candidates()):
                kwargs: dict[str, Any] = {
                    "login_timeout": 8,
                    "network_timeout": 15,
                    "socket_timeout": 15,
                }
                if connection_name:
                    kwargs["connection_name"] = connection_name
                self.connection = snowflake.connector.connect(**kwargs)
            else:
                database, schema = snowflake_namespace()
                kwargs = {
                    "account": env("SNOWFLAKE_ACCOUNT"),
                    "user": env("SNOWFLAKE_USER"),
                    "password": env("SNOWFLAKE_PASSWORD"),
                    "authenticator": env("SNOWFLAKE_AUTHENTICATOR", "snowflake"),
                    "warehouse": env("SNOWFLAKE_WAREHOUSE"),
                    "database": database,
                    "schema": schema,
                    "role": env("SNOWFLAKE_ROLE"),
                    "login_timeout": 8,
                    "network_timeout": 15,
                    "socket_timeout": 15,
                }
                self.connection = snowflake.connector.connect(
                    **{key: value for key, value in kwargs.items() if value is not None}
                )
            self.diagnostic = "Snowflake connection established"
            return True
        except Exception as exc:  # Connector errors vary by auth method and version.
            self.connection = None
            self.diagnostic = f"Snowflake connection unavailable ({type(exc).__name__})"
            return False

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def execute_scalar(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        if not self.connected:
            raise RuntimeError("Snowflake is not connected")
        with self.connection.cursor() as cursor:
            cursor.execute(sql, params)
            row = cursor.fetchone()
        return row[0] if row else None

    def fetch_customer_360(self) -> pd.DataFrame:
        """Fetch the Snowflake view without requiring pandas connector extras."""

        if not self.connected:
            raise RuntimeError("Snowflake is not connected")
        database, schema = snowflake_namespace()
        with self.connection.cursor() as cursor:
            try:
                cursor.execute(f'SELECT * FROM "{database}"."{schema}"."CUSTOMER_360"')
            except Exception:
                cursor.execute("SELECT * FROM CUSTOMER_360")
            rows = cursor.fetchall()
            columns = [column[0].lower() for column in cursor.description]
        return pd.DataFrame(rows, columns=columns)

    def ai_complete(self, prompt: str) -> str:
        """Execute the current Snowflake AI completion function."""

        result = self.execute_scalar("SELECT AI_COMPLETE(%s, %s)", (self.ai_model, prompt))
        if result is None:
            raise RuntimeError("AI_COMPLETE returned no result")
        return str(result)

    def ai_sentiment(self, text: str) -> str:
        """Return the overall label from the current AI_SENTIMENT object."""

        result = self.execute_scalar("SELECT AI_SENTIMENT(%s)", (text,))
        if result is None:
            raise RuntimeError("AI_SENTIMENT returned no result")
        if isinstance(result, str):
            result = json.loads(result)
        categories = result.get("categories", []) if isinstance(result, dict) else []
        overall = next((item for item in categories if item.get("name") == "overall"), None)
        if not overall:
            raise RuntimeError("AI_SENTIMENT returned an unexpected result")
        return str(overall["sentiment"]).upper()
