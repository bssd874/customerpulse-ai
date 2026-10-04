"""Dataset loading and validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import pandas as pd

from src.config import CUSTOMER_FILES


EXPECTED_COLUMNS = {
    "customers": {
        "customer_id",
        "name",
        "email",
        "segment",
        "region",
        "customer_since",
        "product",
        "annual_income",
        "lifetime_value",
    },
    "transactions": {
        "transaction_id",
        "customer_id",
        "transaction_date",
        "amount",
        "transaction_type",
        "merchant_category",
        "status",
    },
    "support_tickets": {
        "ticket_id",
        "customer_id",
        "created_at",
        "category",
        "priority",
        "status",
        "summary",
    },
    "call_transcripts": {
        "call_id",
        "customer_id",
        "call_date",
        "agent_name",
        "transcript",
    },
}


@dataclass(frozen=True)
class DataValidation:
    valid: bool
    errors: tuple[str, ...]


def load_data(files: Mapping[str, Path] | None = None) -> dict[str, pd.DataFrame]:
    """Load all source files and parse typed columns."""

    paths = dict(files or CUSTOMER_FILES)
    missing = [str(path) for path in paths.values() if not Path(path).exists()]
    if missing:
        raise FileNotFoundError(f"Missing required data files: {', '.join(missing)}")

    frames = {name: pd.read_csv(path) for name, path in paths.items()}
    frames["customers"]["customer_since"] = pd.to_datetime(
        frames["customers"]["customer_since"], errors="raise"
    )
    frames["transactions"]["transaction_date"] = pd.to_datetime(
        frames["transactions"]["transaction_date"], errors="raise"
    )
    frames["support_tickets"]["created_at"] = pd.to_datetime(
        frames["support_tickets"]["created_at"], errors="raise"
    )
    frames["call_transcripts"]["call_date"] = pd.to_datetime(
        frames["call_transcripts"]["call_date"], errors="raise"
    )

    validation = validate_data(frames)
    if not validation.valid:
        raise ValueError("Dataset validation failed: " + "; ".join(validation.errors))
    return frames


def validate_data(frames: Mapping[str, pd.DataFrame]) -> DataValidation:
    """Validate schemas, identifiers, enumerations, and foreign keys."""

    errors: list[str] = []
    for name, required in EXPECTED_COLUMNS.items():
        if name not in frames:
            errors.append(f"Missing dataset: {name}")
            continue
        missing = sorted(required - set(frames[name].columns))
        if missing:
            errors.append(f"{name} missing columns: {', '.join(missing)}")

    if errors:
        return DataValidation(False, tuple(errors))

    customers = frames["customers"]
    if customers["customer_id"].duplicated().any():
        errors.append("customers contains duplicate customer_id values")
    if customers["email"].duplicated().any():
        errors.append("customers contains duplicate email values")
    if (customers[["annual_income", "lifetime_value"]].lt(0)).any().any():
        errors.append("customer financial values must be non-negative")

    known_ids = set(customers["customer_id"])
    for name in ("transactions", "support_tickets", "call_transcripts"):
        unknown = set(frames[name]["customer_id"]) - known_ids
        if unknown:
            errors.append(f"{name} contains unknown customer IDs: {sorted(unknown)}")

    transaction_statuses = set(frames["transactions"]["status"])
    if not transaction_statuses <= {"SUCCESS", "FAILED", "DECLINED"}:
        errors.append("transactions contains an unsupported status")
    ticket_statuses = set(frames["support_tickets"]["status"])
    if not ticket_statuses <= {"OPEN", "RESOLVED", "ESCALATED"}:
        errors.append("support_tickets contains an unsupported status")
    if (frames["transactions"]["amount"] <= 0).any():
        errors.append("transaction amounts must be positive")

    return DataValidation(not errors, tuple(errors))

