"""Generate deterministic CustomerPulse demo data and Snowflake seed SQL."""

from __future__ import annotations

import csv
import random
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data"
SQL_DIR = ROOT / "sql"
ANCHOR = date(2026, 9, 30)
RNG = random.Random(42)


CUSTOMERS = [
    ("C001", "Sarah Khan", "sarah.khan@example.com", "PREMIUM", "GCC - UAE", "2018-04-12", "Platinum Card", 185000, 248500),
    ("C002", "Omar Al-Farsi", "omar.alfarsi@example.com", "PREMIUM", "GCC - Oman", "2019-08-21", "Wealth Account", 168000, 206400),
    ("C003", "Layla Haddad", "layla.haddad@example.com", "AFFLUENT", "GCC - UAE", "2020-02-14", "Travel Card", 124000, 143200),
    ("C004", "Yousef Al-Sabah", "yousef.alsabah@example.com", "PREMIUM", "GCC - Kuwait", "2017-11-02", "Premier Banking", 212000, 285700),
    ("C005", "Noor Rahman", "noor.rahman@example.com", "MASS", "GCC - Bahrain", "2023-01-19", "Everyday Account", 61000, 35400),
    ("C006", "Faisal Nasser", "faisal.nasser@example.com", "AFFLUENT", "GCC - Saudi Arabia", "2021-06-10", "Rewards Card", 118000, 119800),
    ("C007", "Mariam Saleh", "mariam.saleh@example.com", "MASS", "GCC - Qatar", "2022-09-05", "Digital Account", 74000, 48200),
    ("C008", "Khalid Mansour", "khalid.mansour@example.com", "SME", "GCC - UAE", "2019-03-27", "Business Card", 156000, 176300),
    ("C009", "Aisha Karim", "aisha.karim@example.com", "AFFLUENT", "GCC - Qatar", "2020-12-08", "Miles Card", 132000, 154900),
    ("C010", "Hamad Al-Thani", "hamad.althani@example.com", "PREMIUM", "GCC - Qatar", "2016-07-16", "Private Banking", 260000, 342600),
    ("C011", "Rania Farouk", "rania.farouk@example.com", "MASS", "GCC - Saudi Arabia", "2024-02-01", "Cashback Card", 68000, 26800),
    ("C012", "Tariq Mahmoud", "tariq.mahmoud@example.com", "SME", "GCC - Bahrain", "2018-10-23", "Business Account", 149000, 164500),
    ("C013", "Dana Ibrahim", "dana.ibrahim@example.com", "AFFLUENT", "GCC - Kuwait", "2021-04-30", "Signature Card", 127000, 131700),
    ("C014", "Zain Malik", "zain.malik@example.com", "MASS", "GCC - Oman", "2023-06-18", "Everyday Card", 72000, 41600),
]


def transaction_rows() -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = [
        ("TX0001", "C001", "2026-01-15", 5200.00, "CARD_PURCHASE", "Travel", "SUCCESS"),
        ("TX0002", "C001", "2026-04-20", 4800.00, "CARD_PURCHASE", "Luxury Retail", "SUCCESS"),
        ("TX0003", "C001", "2026-05-15", 5600.00, "CARD_PURCHASE", "Travel", "SUCCESS"),
        ("TX0004", "C001", "2026-06-15", 6200.00, "CARD_PURCHASE", "Hospitality", "SUCCESS"),
        ("TX0005", "C001", "2026-07-15", 2500.00, "CARD_PURCHASE", "Travel", "SUCCESS"),
        ("TX0006", "C001", "2026-08-10", 2350.00, "CARD_PURCHASE", "Dining", "SUCCESS"),
        ("TX0007", "C001", "2026-08-25", 1800.00, "CARD_PURCHASE", "Overseas Retail", "FAILED"),
        ("TX0008", "C001", "2026-09-12", 2100.00, "CARD_PURCHASE", "Travel", "SUCCESS"),
        ("TX0009", "C001", "2026-09-20", 1600.00, "CARD_PURCHASE", "Overseas Retail", "DECLINED"),
    ]
    profiles = {
        "C002": (3100, 1.00, set()),
        "C003": (2200, 0.55, {6}),
        "C004": (3900, 1.10, set()),
        "C005": (780, 0.85, {5}),
        "C006": (2050, 0.72, set()),
        "C007": (920, 1.20, set()),
        "C008": (2850, 0.65, {4}),
        "C009": (2350, 1.05, set()),
        "C010": (4600, 0.92, set()),
        "C011": (680, 0.42, {5, 6}),
        "C012": (2700, 1.18, set()),
        "C013": (2100, 0.78, {4}),
        "C014": (840, 1.08, set()),
    }
    offsets = [300, 220, 160, 125, 75, 40, 15]
    tx_types = ["CARD_PURCHASE", "TRANSFER", "BILL_PAYMENT"]
    categories = ["Dining", "Travel", "Retail", "Utilities", "Groceries", "Hospitality"]
    tx_number = 10
    for customer_id, (base, recent_factor, failures) in profiles.items():
        for index, offset in enumerate(offsets):
            is_recent = offset <= 90
            amount_factor = recent_factor if is_recent else 1.0
            variation = 0.88 + RNG.random() * 0.24
            amount = round(base * amount_factor * variation, 2)
            status = "SUCCESS"
            if index in failures:
                status = "FAILED" if index % 2 else "DECLINED"
            rows.append(
                (
                    f"TX{tx_number:04d}",
                    customer_id,
                    (ANCHOR - timedelta(days=offset)).isoformat(),
                    amount,
                    RNG.choice(tx_types),
                    RNG.choice(categories),
                    status,
                )
            )
            tx_number += 1
    return rows


SUPPORT_TICKETS = [
    ("TK001", "C001", "2026-07-02", "Card", "MEDIUM", "RESOLVED", "Travel notification was not reflected immediately."),
    ("TK002", "C001", "2026-08-26", "Transactions", "HIGH", "ESCALATED", "Overseas card purchase declined despite travel notice."),
    ("TK003", "C001", "2026-09-08", "Card", "HIGH", "OPEN", "Card restriction remains after identity verification."),
    ("TK004", "C001", "2026-09-21", "Transactions", "URGENT", "ESCALATED", "Second overseas transaction declined after repeated support contact."),
    ("TK005", "C002", "2026-03-18", "Digital Banking", "LOW", "RESOLVED", "Requested biometric login reset."),
    ("TK006", "C002", "2026-08-11", "Statement", "LOW", "RESOLVED", "Requested an annual fee statement copy."),
    ("TK007", "C003", "2026-08-19", "Rewards", "MEDIUM", "OPEN", "Missing travel reward points from two purchases."),
    ("TK008", "C003", "2026-09-17", "Transactions", "HIGH", "ESCALATED", "Merchant reversal has not appeared on the account."),
    ("TK009", "C004", "2026-05-04", "Relationship", "LOW", "RESOLVED", "Requested relationship manager callback."),
    ("TK010", "C004", "2026-09-03", "Transfer", "LOW", "RESOLVED", "Beneficiary activation needed confirmation."),
    ("TK011", "C005", "2026-08-20", "Fees", "MEDIUM", "OPEN", "Asked for clarification on a late payment fee."),
    ("TK012", "C005", "2026-09-12", "Card", "MEDIUM", "RESOLVED", "Replacement card delivery tracking request."),
    ("TK013", "C006", "2026-06-14", "Rewards", "LOW", "RESOLVED", "Reward redemption option was temporarily unavailable."),
    ("TK014", "C006", "2026-09-07", "Digital Banking", "MEDIUM", "OPEN", "Spending insights are not refreshing in the mobile app."),
    ("TK015", "C007", "2026-04-22", "Transfer", "LOW", "RESOLVED", "Local transfer confirmation was delayed."),
    ("TK016", "C008", "2026-07-30", "Business Card", "MEDIUM", "OPEN", "Employee card limit change is pending."),
    ("TK017", "C008", "2026-09-18", "Transactions", "HIGH", "ESCALATED", "Supplier payment was declined close to invoice due date."),
    ("TK018", "C009", "2026-02-12", "Travel", "LOW", "RESOLVED", "Airport lounge eligibility question."),
    ("TK019", "C009", "2026-08-05", "Rewards", "LOW", "RESOLVED", "Miles transfer completed later than expected."),
    ("TK020", "C010", "2026-01-28", "Relationship", "LOW", "RESOLVED", "Portfolio review appointment rescheduled."),
    ("TK021", "C010", "2026-09-10", "Statement", "LOW", "RESOLVED", "Requested consolidated account statement."),
    ("TK022", "C011", "2026-08-07", "Card", "HIGH", "OPEN", "Contactless payments fail at several merchants."),
    ("TK023", "C011", "2026-09-16", "Transactions", "HIGH", "ESCALATED", "Two card payments were declined after PIN reset."),
    ("TK024", "C012", "2026-04-13", "Business Account", "MEDIUM", "RESOLVED", "Bulk payment template required an update."),
    ("TK025", "C012", "2026-09-02", "Transfer", "LOW", "RESOLVED", "International beneficiary document review completed."),
    ("TK026", "C013", "2026-08-16", "Card", "MEDIUM", "OPEN", "Card upgrade benefit date needs confirmation."),
    ("TK027", "C013", "2026-09-19", "Transactions", "MEDIUM", "RESOLVED", "Restaurant transaction duplicated and then reversed."),
    ("TK028", "C014", "2026-05-20", "Digital Banking", "LOW", "RESOLVED", "Mobile number update verification assistance."),
    ("TK029", "C014", "2026-09-01", "Fees", "LOW", "RESOLVED", "Monthly account fee explanation provided."),
    ("TK030", "C007", "2026-09-25", "Digital Banking", "LOW", "RESOLVED", "Push notification settings were restored."),
]


CALL_TRANSCRIPTS = [
    ("CL001", "C001", "2026-07-03", "Maya", "Thank you for helping with the travel notice. I hope the card works normally overseas."),
    ("CL002", "C001", "2026-09-23", "Ahmed", "I am frustrated that overseas transactions are still being declined. I have contacted support repeatedly, the card restriction is still not resolved, and I am concerned I may need to move to another provider if this continues."),
    ("CL003", "C002", "2026-08-12", "Salma", "The annual statement was clear. Thank you, the service has been helpful."),
    ("CL004", "C003", "2026-09-20", "Nabil", "I am disappointed that the reversal is still not visible and I have been waiting for an update."),
    ("CL005", "C004", "2026-09-04", "Maya", "The beneficiary is active now. I appreciate the quick confirmation."),
    ("CL006", "C005", "2026-09-13", "Reem", "The replacement card arrived, but I still have a question about the fee."),
    ("CL007", "C006", "2026-09-09", "Ahmed", "The app issue is inconvenient. Please let me know when the spending view is resolved."),
    ("CL008", "C007", "2026-09-26", "Salma", "Everything works well again and the notification issue was resolved. Thank you."),
    ("CL009", "C008", "2026-09-20", "Nabil", "The declined supplier payment created a problem for the business. I need a clear resolution quickly."),
    ("CL010", "C009", "2026-08-07", "Reem", "The miles arrived and I am satisfied with the explanation."),
    ("CL011", "C010", "2026-09-11", "Maya", "The consolidated statement is exactly what I needed. Excellent support."),
    ("CL012", "C011", "2026-09-18", "Ahmed", "The two declined payments were inconvenient. Please confirm when the card issue is resolved."),
    ("CL013", "C012", "2026-09-03", "Salma", "The document review was completed and our transfer process works well now."),
    ("CL014", "C013", "2026-09-20", "Nabil", "The duplicate transaction was resolved, but I am waiting for confirmation of the upgrade benefits."),
    ("CL015", "C014", "2026-09-02", "Reem", "Thank you for explaining the account fee. The answer was helpful."),
    ("CL016", "C003", "2026-06-11", "Maya", "I was happy with the travel card until the recent reward issue."),
    ("CL017", "C008", "2026-05-07", "Ahmed", "The business account has been reliable and the team was helpful."),
    ("CL018", "C011", "2026-05-29", "Salma", "Contactless payment usually works well, so the recent issue is surprising."),
]


def write_csv(path: Path, headers: Iterable[str], rows: Iterable[Iterable[object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def insert_sql(table: str, columns: list[str], rows: list[tuple[object, ...]]) -> str:
    values = ",\n".join("(" + ", ".join(sql_literal(value) for value in row) + ")" for row in rows)
    return f"INSERT INTO {table} ({', '.join(columns)}) VALUES\n{values};\n"


def write_seed_sql(
    transactions: list[tuple[object, ...]],
) -> None:
    sections = [
        "-- Deterministic synthetic demo data. Regenerate with: python scripts/seed_data.py\n",
        "USE DATABASE CUSTOMERPULSE_DB;\nUSE SCHEMA APP;\n",
        "TRUNCATE TABLE CALL_TRANSCRIPTS;\nTRUNCATE TABLE SUPPORT_TICKETS;\nTRUNCATE TABLE TRANSACTIONS;\nTRUNCATE TABLE CUSTOMERS;\n",
        insert_sql(
            "CUSTOMERS",
            ["customer_id", "name", "email", "segment", "region", "customer_since", "product", "annual_income", "lifetime_value"],
            CUSTOMERS,
        ),
        insert_sql(
            "TRANSACTIONS",
            ["transaction_id", "customer_id", "transaction_date", "amount", "transaction_type", "merchant_category", "status"],
            transactions,
        ),
        insert_sql(
            "SUPPORT_TICKETS",
            ["ticket_id", "customer_id", "created_at", "category", "priority", "status", "summary"],
            SUPPORT_TICKETS,
        ),
        insert_sql(
            "CALL_TRANSCRIPTS",
            ["call_id", "customer_id", "call_date", "agent_name", "transcript"],
            CALL_TRANSCRIPTS,
        ),
    ]
    (SQL_DIR / "02_seed.sql").write_text("\n".join(sections), encoding="utf-8")


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SQL_DIR.mkdir(parents=True, exist_ok=True)
    transactions = transaction_rows()
    write_csv(
        DATA_DIR / "customers.csv",
        ["customer_id", "name", "email", "segment", "region", "customer_since", "product", "annual_income", "lifetime_value"],
        CUSTOMERS,
    )
    write_csv(
        DATA_DIR / "transactions.csv",
        ["transaction_id", "customer_id", "transaction_date", "amount", "transaction_type", "merchant_category", "status"],
        transactions,
    )
    write_csv(
        DATA_DIR / "support_tickets.csv",
        ["ticket_id", "customer_id", "created_at", "category", "priority", "status", "summary"],
        SUPPORT_TICKETS,
    )
    write_csv(
        DATA_DIR / "call_transcripts.csv",
        ["call_id", "customer_id", "call_date", "agent_name", "transcript"],
        CALL_TRANSCRIPTS,
    )
    write_seed_sql(transactions)
    print(
        f"Generated {len(CUSTOMERS)} customers, {len(transactions)} transactions, "
        f"{len(SUPPORT_TICKETS)} tickets, and {len(CALL_TRANSCRIPTS)} transcripts."
    )


if __name__ == "__main__":
    main()
