"""Evidence-grounded Snowflake AI calls with polished deterministic fallbacks."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping

from src.snowflake_client import SnowflakeClient


def _reasons(context: Mapping[str, Any]) -> list[str]:
    explanations = context.get("risk_explanations") or []
    return [
        f"+{int(item['points'])} {item['reason']}"
        for item in explanations
        if isinstance(item, Mapping) and "points" in item and "reason" in item
    ]


def _evidence_json(context: Mapping[str, Any]) -> str:
    safe = {
        key: value
        for key, value in context.items()
        if key
        in {
            "name",
            "segment",
            "product",
            "lifetime_value",
            "transaction_change_pct",
            "recent_failed_transactions",
            "unresolved_tickets",
            "latest_ticket_summary",
            "latest_call_transcript",
            "sentiment_label",
            "snowflake_sentiment_label",
            "sentiment_source",
            "risk_score",
            "risk_tier",
            "risk_explanations",
        }
    }
    return json.dumps(safe, default=str, ensure_ascii=False)


def explain_risk(
    customer_context: Mapping[str, Any], client: SnowflakeClient | None = None
) -> dict[str, str]:
    """Explain risk using Snowflake AI when possible, otherwise rules only."""

    if client is not None and client.connected:
        prompt = (
            "You are an enterprise customer-retention analyst. Use ONLY the supplied Customer 360 "
            "evidence. Do not invent products, events, complaints, transactions, financial amounts, "
            "customer history, or protected traits. The deterministic risk score is authoritative; "
            "explain it but never recalculate it. Mention the most important signals. In at most 90 words, "
            "be concise, grounded, and suitable for a relationship manager.\nEVIDENCE:\n"
            + _evidence_json(customer_context)
        )
        try:
            return {
                "text": client.ai_complete(prompt),
                "source": "snowflake_ai",
                "model": client.working_ai_model or "account-verified model",
            }
        except Exception:
            pass

    reasons = _reasons(customer_context)
    name = str(customer_context.get("name", "This customer"))
    tier = str(customer_context.get("risk_tier", "LOW")).lower()
    score = int(customer_context.get("risk_score", 0))
    if reasons:
        joined = "; ".join(reason.removeprefix("+") for reason in reasons)
        text = f"{name} is {tier} risk ({score}/100) because the rules detected: {joined}."
    else:
        text = f"{name} is {tier} risk ({score}/100); no configured risk trigger is currently active."
    return {"text": text, "source": "deterministic"}


ACTION_FIELDS = {
    "priority": "priority",
    "recommended action": "recommended_action",
    "why": "why",
    "suggested outreach": "suggested_outreach",
    "business objective": "business_objective",
}


def parse_next_best_action(response: str) -> dict[str, str] | None:
    """Parse either JSON or strongly labelled AI_COMPLETE output."""

    text = response.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        decoded = None
    if isinstance(decoded, Mapping):
        parsed_json = {
            target: str(decoded.get(target, decoded.get(label, ""))).strip()
            for label, target in ACTION_FIELDS.items()
        }
        if all(parsed_json.values()):
            return parsed_json

    parsed: dict[str, str] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        line = re.sub(r"^[\s*#>-]+", "", raw_line).strip()
        line = line.replace("**", "")
        if not line:
            continue
        matched = False
        for label, key in ACTION_FIELDS.items():
            match = re.match(rf"^{re.escape(label)}\s*:\s*(.*)$", line, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if value:
                    parsed[key] = value
                current_key = key
                matched = True
                break
        if not matched and current_key:
            parsed[current_key] = f"{parsed.get(current_key, '')} {line}".strip()
    return parsed if all(key in parsed and parsed[key] for key in ACTION_FIELDS.values()) else None


def _fallback_action(context: Mapping[str, Any]) -> dict[str, str]:
    tier = str(context.get("risk_tier", "LOW"))
    unresolved = int(context.get("unresolved_tickets", 0))
    failures = int(context.get("recent_failed_transactions", 0))
    decline = float(context.get("transaction_change_pct", 0))
    name = str(context.get("name", "the customer"))
    issue = str(context.get("latest_ticket_summary", "the open service issue")).rstrip(".!? ")

    if tier == "HIGH":
        priority = "P1 — Contact within 24 hours"
        action = "Assign a senior retention specialist and resolve the service blocker end to end."
        why_parts = []
        if unresolved:
            why_parts.append(f"{unresolved} unresolved support cases")
        if failures:
            why_parts.append(f"{failures} recent failed transactions")
        if decline <= -20:
            why_parts.append(f"a {abs(decline):.0f}% transaction-value decline")
        why = "The intervention is triggered by " + ", ".join(why_parts) + "."
        outreach = (
            f"Hi {name}, I’m following up personally about {issue.lower()}. "
            "I’ll coordinate ownership through resolution and confirm the next steps with you today."
        )
        objective = "Remove the immediate friction, restore confidence, and retain a high-value relationship."
    elif tier == "MEDIUM":
        priority = "P2 — Review within 3 business days"
        action = "Proactively review the account and close the highest-impact unresolved issue."
        why = "Multiple early-warning signals merit outreach before they compound into attrition risk."
        outreach = (
            f"Hi {name}, we noticed your recent experience may not have been seamless. "
            "Can we review the outstanding issue and make sure everything is working as expected?"
        )
        objective = "Prevent escalation and return engagement to its prior level."
    else:
        priority = "P3 — Maintain regular service cadence"
        action = "Continue normal relationship monitoring and recognize positive engagement."
        why = "No material combination of risk triggers is active in the current observation window."
        outreach = f"Hi {name}, thank you for your continued relationship with us."
        objective = "Sustain satisfaction and identify relevant growth opportunities."

    return {
        "priority": priority,
        "recommended_action": action,
        "why": why,
        "suggested_outreach": outreach,
        "business_objective": objective,
        "source": "deterministic",
    }


def generate_next_best_action(
    customer_context: Mapping[str, Any], client: SnowflakeClient | None = None
) -> dict[str, str]:
    """Generate a structured next action, never hiding deterministic fallback."""

    if client is not None and client.connected:
        prompt = (
            "You are an enterprise retention decision engine. Use ONLY the supplied Customer 360 evidence. "
            "Do not invent facts, discounts, fees, compensation, legal claims, products outside the known "
            "customer product, probabilities, or guaranteed outcomes. Return exactly five concise lines "
            "using these labels: Priority:, Recommended Action:, Why:, Suggested Outreach:, Business "
            "Objective:. Keep the recommendation specific, humane, and operational.\nEVIDENCE:\n"
            + _evidence_json(customer_context)
        )
        try:
            response = client.ai_complete(prompt)
            parsed = parse_next_best_action(response)
            if parsed:
                parsed["source"] = "snowflake_ai"
                parsed["model"] = client.working_ai_model or "account-verified model"
                return parsed
        except Exception:
            pass
    return _fallback_action(customer_context)
