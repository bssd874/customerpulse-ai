"""Central configuration for CustomerPulse AI."""

from __future__ import annotations

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
SQL_DIR = ROOT_DIR / "sql"

DEFAULT_DATABASE = "CUSTOMERPULSE_DB"
DEFAULT_SCHEMA = "APP"
DEFAULT_AI_MODEL = "llama3.3-70b"

CUSTOMER_FILES = {
    "customers": DATA_DIR / "customers.csv",
    "transactions": DATA_DIR / "transactions.csv",
    "support_tickets": DATA_DIR / "support_tickets.csv",
    "call_transcripts": DATA_DIR / "call_transcripts.csv",
}


def env(name: str, default: str | None = None) -> str | None:
    """Read a configuration value without logging it."""

    value = os.getenv(name)
    return value if value not in (None, "") else default


def snowflake_namespace() -> tuple[str, str]:
    """Return the desired Snowflake database and schema."""

    return (
        env("SNOWFLAKE_DATABASE", DEFAULT_DATABASE) or DEFAULT_DATABASE,
        env("SNOWFLAKE_SCHEMA", DEFAULT_SCHEMA) or DEFAULT_SCHEMA,
    )

