# Ready-to-Paste Submission Copy

## Project name

CustomerPulse AI

## Tagline

From fragmented customer signals to the next best action.

## Challenge

Snowflake CoCo CLI Hackathon — GCC Edition  
Challenge 02: Customer 360 & Next Best Action Engine

## Problem

Customer attrition risk is hidden across disconnected systems. A high-value customer can reduce spend, experience payment failures, open repeated support cases, and express frustration in a call without any single team seeing the full pattern early enough to act.

## Solution

CustomerPulse AI combines structured customer profiles, transactions, and support tickets with unstructured call transcripts. It produces one Customer 360, a transparent 0–100 risk score, a concise risk explanation, and a Next Best Action with priority, rationale, outreach language, and business objective.

## Key features

- Portfolio-level risk and customer-value prioritization.
- Customer 360 joining four data domains.
- Explainable deterministic risk factors and tier boundaries.
- Current Snowflake `AI_SENTIMENT` and `AI_COMPLETE` integration paths.
- Clear deterministic fallback when Snowflake AI is unavailable.
- Data-grounded question routing for common retention questions.
- Fully runnable local Streamlit demo.

## Architecture summary

CSV demo sources feed an equivalent pandas and Snowflake SQL aggregation layer. Customer features pass through deterministic risk rules. Streamlit presents portfolio, Customer 360, recommendation, and controlled Q&A views. When a configured Snowflake connection and Cortex privileges are available, `AI_SENTIMENT` enriches transcript understanding and `AI_COMPLETE` generates evidence-constrained explanations and actions; otherwise deterministic templates preserve complete functionality.

## Snowflake technologies used

- Snowflake tables for customers, transactions, tickets, and transcripts.
- `CUSTOMER_360` SQL view using CTEs, window functions, conditional aggregation, and deterministic scoring.
- Optional `CUSTOMER_360_AI` view using current `AI_SENTIMENT`.
- Application generation path using current `AI_COMPLETE`.
- Snowflake Python Connector with standard configuration and environment-variable support.

Live Snowflake execution was not available in the build environment, so cloud behavior is not claimed as validated.

## CoCo CLI usage

CoCo CLI was not installed or authenticated in the build environment. No CoCo execution or contribution is claimed. The repository documents the detection result and the bounded SQL-review task intended for a future authenticated run.

## Innovation

CustomerPulse AI does not hide churn risk behind a black-box label. It preserves the chain from raw operational evidence to points, tier, explanation, and next action. Its dual execution path also separates product value from demo infrastructure: the same business logic remains inspectable and runnable without cloud credentials.

## Business impact

The product helps retention and service leaders prioritize scarce human attention by both risk and customer value. Earlier intervention can protect lifetime value, reduce repeat contacts, shorten unresolved-case duration, and give relationship managers consistent evidence for outreach.

## Roadmap

Next steps are governed Snowflake ingestion, outcome-based score calibration, CRM work-queue integration, offer-eligibility controls, and multilingual GCC voice analysis.

