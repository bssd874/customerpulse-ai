"""Create and validate CustomerPulse objects using an available Snowflake connection."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import SQL_DIR, snowflake_namespace
from src.snowflake_client import SnowflakeClient


SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def identifier(value: str) -> str:
    if not SAFE_IDENTIFIER.fullmatch(value):
        raise ValueError(f"Unsafe Snowflake identifier: {value!r}")
    return f'"{value.upper()}"'


def statements(sql: str) -> list[str]:
    """Split project SQL; project seed strings contain no semicolons."""

    return [statement.strip() for statement in sql.split(";") if statement.strip()]


def ensure_namespace(client: SnowflakeClient) -> tuple[str, str]:
    desired_database, desired_schema = snowflake_namespace()
    cursor = client.connection.cursor()
    try:
        try:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {identifier(desired_database)}")
            database = desired_database.upper()
        except Exception:
            cursor.execute("SELECT CURRENT_DATABASE()")
            database = cursor.fetchone()[0]
            if not database:
                raise RuntimeError("No usable database and CREATE DATABASE is not permitted")
        cursor.execute(f"USE DATABASE {identifier(database)}")

        try:
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {identifier(database)}.{identifier(desired_schema)}")
            schema = desired_schema.upper()
        except Exception:
            cursor.execute("SELECT CURRENT_SCHEMA()")
            schema = cursor.fetchone()[0]
            if not schema:
                raise RuntimeError("No usable schema and CREATE SCHEMA is not permitted")
        cursor.execute(f"USE SCHEMA {identifier(schema)}")
        return database, schema
    finally:
        cursor.close()


def namespace_sql(sql: str, database: str, schema: str) -> str:
    return sql.replace("CUSTOMERPULSE_DB.APP", f"{database}.{schema}").replace(
        "USE DATABASE CUSTOMERPULSE_DB", f"USE DATABASE {identifier(database)}"
    ).replace("USE SCHEMA APP", f"USE SCHEMA {identifier(schema)}")


def run_file(client: SnowflakeClient, path: Path, database: str, schema: str) -> None:
    sql = namespace_sql(path.read_text(encoding="utf-8"), database, schema)
    with client.connection.cursor() as cursor:
        for statement in statements(sql):
            try:
                cursor.execute(statement)
            except Exception as exc:
                if "CUSTOMER_360_AI" in statement or "AI_SENTIMENT" in statement:
                    print(f"Optional AI sentiment view skipped ({type(exc).__name__}).")
                    continue
                raise
    print(f"Applied {path.name}")


def object_exists(client: SnowflakeClient, database: str, schema: str, name: str) -> bool:
    """Check a project object without changing it."""

    sql = (
        f"SELECT COUNT(*) FROM {identifier(database)}.INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s"
    )
    with client.connection.cursor() as cursor:
        cursor.execute(sql, (schema.upper(), name.upper()))
        return int(cursor.fetchone()[0]) > 0


def table_count(client: SnowflakeClient, database: str, schema: str, name: str) -> int:
    qualified = f"{identifier(database)}.{identifier(schema)}.{identifier(name)}"
    with client.connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM {qualified}")
        return int(cursor.fetchone()[0])


def main() -> int:
    client = SnowflakeClient()
    if not client.connect():
        print(f"Snowflake setup not run: {client.diagnostic}")
        return 2

    try:
        database, schema = ensure_namespace(client)
        print(f"Using Snowflake namespace {database}.{schema}")
        table_names = ("CUSTOMERS", "TRANSACTIONS", "SUPPORT_TICKETS", "CALL_TRANSCRIPTS")
        existing_tables = {
            name: object_exists(client, database, schema, name) for name in table_names
        }
        if not all(existing_tables.values()):
            run_file(client, SQL_DIR / "01_tables.sql", database, schema)

        counts = {
            name: table_count(client, database, schema, name) for name in table_names
        }
        if all(count == 0 for count in counts.values()):
            run_file(client, SQL_DIR / "02_seed.sql", database, schema)
        elif any(count == 0 for count in counts.values()):
            raise RuntimeError(
                "Partial existing CustomerPulse data detected; refusing to overwrite populated tables"
            )
        else:
            print("Existing CustomerPulse tables contain data; seed step skipped.")

        if not object_exists(client, database, schema, "CUSTOMER_360"):
            run_file(client, SQL_DIR / "03_customer_360.sql", database, schema)
        else:
            print("Existing CUSTOMER_360 found; view creation skipped.")
        with client.connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM CUSTOMER_360")
            customer_count = int(cursor.fetchone()[0])
            cursor.execute(
                "SELECT risk_score, risk_tier FROM CUSTOMER_360 WHERE name = 'Sarah Khan'"
            )
            sarah = cursor.fetchone()
        if customer_count < 12 or not sarah or sarah[1] != "HIGH":
            raise RuntimeError("Snowflake validation did not produce the expected demo scenario")
        print(
            f"Validation passed: {customer_count} customers; Sarah Khan is {sarah[1]} risk "
            f"at {int(sarah[0])}/100."
        )
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
