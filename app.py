"""CustomerPulse AI Streamlit dashboard."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from src.ai import explain_risk, generate_next_best_action
from src.analytics import build_customer_360, customer_context
from src.data import load_data
from src.snowflake_client import SnowflakeClient
from src.ui import (
    APP_CSS,
    answer_customer_question,
    money,
    relationship_years,
    risk_badge,
    risk_contribution_text,
    trend,
)


def local_snapshot() -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    frames = load_data()
    return frames, build_customer_360(frames)


def snowflake_client() -> SnowflakeClient:
    try:
        section = st.secrets.get("snowflake", {})
        secrets = {"snowflake": dict(section)} if section else None
    except (FileNotFoundError, KeyError, TypeError, ValueError):
        secrets = None
    client = SnowflakeClient(secrets=secrets)
    if client.connect():
        client.probe_ai_capabilities()
    return client


def _card(label: str, value: str) -> None:
    st.markdown(
        f'<div class="cp-card"><div class="cp-label">{label}</div>'
        f'<div class="cp-value">{value}</div></div>',
        unsafe_allow_html=True,
    )


def _risk_style(row: pd.Series) -> list[str]:
    color = {
        "HIGH": "background-color: #fee2e2; color: #991b1b",
        "MEDIUM": "background-color: #fef3c7; color: #92400e",
        "LOW": "background-color: #d1fae5; color: #065f46",
    }.get(row.get("Risk Tier"), "")
    return [color] * len(row)


def _selected_row(customer_360: pd.DataFrame, name: str) -> pd.Series:
    return customer_360.loc[customer_360["name"].eq(name)].iloc[0]


def _normalize_snowflake_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize connector VARIANT/date values to the local analytics shape."""

    result = frame.copy()

    def explanations(value: object) -> list[dict[str, object]]:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else []
            except json.JSONDecodeError:
                return []
        return []

    result["risk_explanations"] = result["risk_explanations"].map(explanations)
    result["customer_since"] = pd.to_datetime(result["customer_since"])
    return result.sort_values(
        ["risk_score", "lifetime_value"], ascending=[False, False]
    ).reset_index(drop=True)


def resolve_customer_360(
    local_frame: pd.DataFrame, client: SnowflakeClient
) -> tuple[pd.DataFrame, str]:
    """Choose a truthful live dataset or the complete deterministic fallback."""

    local = local_frame.copy()
    local["snowflake_sentiment_label"] = None
    local["sentiment_source"] = "deterministic"
    local["data_source"] = "local"
    if not client.connected:
        return local, "local"
    try:
        live = client.fetch_customer_360()
        if live.empty or not set(local_frame.columns) <= set(live.columns):
            raise ValueError("CUSTOMER_360 is missing required columns")
        live = _normalize_snowflake_frame(live)
    except Exception:
        return local, "local"

    try:
        live = client.enrich_customer_sentiments(live)
    except Exception:
        live["snowflake_sentiment_label"] = None
        live["sentiment_source"] = "deterministic"
    live["data_source"] = "snowflake"
    return live, "snowflake"


def main() -> None:
    st.set_page_config(
        page_title="CustomerPulse AI",
        page_icon="◉",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(APP_CSS, unsafe_allow_html=True)
    st.markdown(
        """
        <div class="cp-hero">
          <div class="cp-eyebrow">SNOWFLAKE CUSTOMER INTELLIGENCE</div>
          <h1>CustomerPulse AI</h1>
          <p>From fragmented customer signals to the next best action.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cached_snapshot = st.cache_data(local_snapshot, show_spinner=False)
    cached_client = st.cache_resource(snowflake_client, show_spinner=False)
    frames, local_customer_360 = cached_snapshot()
    client = cached_client()
    if "customer_360_dataset" not in st.session_state:
        customer_360, data_source = resolve_customer_360(local_customer_360, client)
        st.session_state["customer_360_dataset"] = customer_360
        st.session_state["customer_data_source"] = data_source
    customer_360 = st.session_state["customer_360_dataset"]
    data_source = st.session_state["customer_data_source"]
    live_data = data_source == "snowflake"

    status_col, ai_col, freshness_col = st.columns([2, 2, 4])
    with status_col:
        if live_data:
            st.success("🟢 Live Snowflake")
        else:
            st.warning("🟡 Demo Mode")
    with ai_col:
        if live_data and client.ai_active:
            st.success("🟢 Snowflake AI Active")
        else:
            st.caption("Deterministic AI fallback ready")
    with freshness_col:
        analysis_date = frames["transactions"]["transaction_date"].max()
        source_text = (
            "Customer 360 sourced from Snowflake"
            if live_data
            else "Using deterministic local snapshot"
        )
        st.caption(f"{source_text} · observation date {analysis_date:%d %b %Y}")

    tab_overview, tab_customer, tab_action, tab_ask = st.tabs(
        [
            "📊 Portfolio Overview",
            "👤 Customer 360",
            "✨ Next Best Action",
            "💬 Ask Customer Data",
        ]
    )

    with tab_overview:
        st.subheader("Portfolio risk command center")
        high_risk = customer_360["risk_tier"].eq("HIGH")
        high_value_threshold = customer_360["lifetime_value"].quantile(0.75)
        high_value_at_risk = high_risk & customer_360["lifetime_value"].ge(high_value_threshold)
        metric_columns = st.columns(4)
        metric_columns[0].metric("Total Customers", f"{len(customer_360):,}")
        metric_columns[1].metric("High-Risk Customers", f"{int(high_risk.sum()):,}")
        metric_columns[2].metric("Average Risk Score", f"{customer_360['risk_score'].mean():.1f}")
        metric_columns[3].metric("High-Value Customers at Risk", f"{int(high_value_at_risk.sum()):,}")

        st.markdown("#### Priority customer watchlist")
        display = customer_360[
            [
                "name",
                "segment",
                "lifetime_value",
                "risk_score",
                "risk_tier",
                "sentiment_label",
                "unresolved_tickets",
                "transaction_change_pct",
            ]
        ].copy()
        if "snowflake_sentiment_label" in customer_360:
            display["sentiment_label"] = customer_360["snowflake_sentiment_label"].fillna(
                customer_360["sentiment_label"]
            )
        display = display.rename(
            columns={
                "name": "Customer",
                "segment": "Segment",
                "lifetime_value": "Lifetime Value",
                "risk_score": "Risk Score",
                "risk_tier": "Risk Tier",
                "sentiment_label": "Sentiment",
                "unresolved_tickets": "Unresolved Tickets",
                "transaction_change_pct": "Transaction Trend",
            }
        )
        st.dataframe(
            display.style.apply(_risk_style, axis=1).format(
                {"Lifetime Value": "${:,.0f}", "Transaction Trend": "{:+.1f}%"}
            ),
            width="stretch",
            hide_index=True,
            height=410,
        )
        chart_col, insight_col = st.columns([3, 2])
        with chart_col:
            st.markdown("#### Risk distribution")
            order = ["LOW", "MEDIUM", "HIGH"]
            distribution = (
                customer_360["risk_tier"].value_counts().reindex(order, fill_value=0).rename("Customers")
            )
            st.bar_chart(distribution, color="#0e7490", height=235)
        with insight_col:
            st.markdown("#### Portfolio signal")
            top = customer_360.iloc[0]
            _card("Highest retention priority", f"{top['name']} · {int(top['risk_score'])}/100")
            _card("Largest current value decline", f"{customer_360.loc[customer_360['transaction_change_pct'].idxmin(), 'transaction_change_pct']:.1f}%")
            _card("Open support workload", f"{int(customer_360['unresolved_tickets'].sum())} unresolved cases")

    with tab_customer:
        if live_data:
            st.caption("Customer 360 sourced from Snowflake")
        names = customer_360["name"].tolist()
        default_index = names.index("Sarah Khan") if "Sarah Khan" in names else 0
        selected_name = st.selectbox("Select customer", names, index=default_index, key="customer_360_name")
        row = _selected_row(customer_360, selected_name)

        title_col, risk_col = st.columns([4, 1])
        with title_col:
            st.subheader(row["name"])
            st.caption(f"{row['customer_id']} · {row['segment']} · {row['region']}")
        with risk_col:
            tier = str(row["risk_tier"])
            st.metric("Risk", f"{int(row['risk_score'])}/100")
            st.markdown(risk_badge(tier), unsafe_allow_html=True)

        profile_col, value_col = st.columns([2, 3])
        with profile_col:
            with st.container(border=True):
                st.markdown("#### Profile")
                years = relationship_years(row["customer_since"], analysis_date)
                c1, c2 = st.columns(2)
                c1.metric("Segment", row["segment"])
                c2.metric("Relationship", f"{years:.1f} years")
                st.write(f"**Product:** {row['product']}")
                st.write(f"**Region:** {row['region']}")
        with value_col:
            with st.container(border=True):
                st.markdown("#### Relationship Value")
                c1, c2, c3 = st.columns(3)
                c1.metric("Lifetime Value", money(row["lifetime_value"]))
                c2.metric("Transactions", int(row["total_transactions"]))
                c3.metric("90-day trend", trend(row["transaction_change_pct"]))
                recent_value = money(row["recent_transaction_value"]).replace("$", "\\$")
                previous_value = money(row["previous_transaction_value"]).replace("$", "\\$")
                st.caption(
                    f"Recent successful value {recent_value} vs previous window {previous_value}"
                )

        support_col, voice_col = st.columns(2)
        with support_col:
            with st.container(border=True):
                st.markdown("#### Support Health")
                c1, c2 = st.columns(2)
                c1.metric("Total tickets", int(row["total_tickets"]))
                c2.metric("Unresolved", int(row["unresolved_tickets"]))
                st.markdown("**Most recent issue**")
                st.write(row["latest_ticket_summary"])
        with voice_col:
            with st.container(border=True):
                st.markdown("#### Voice of Customer")
                snowflake_sentiment = row.get("snowflake_sentiment_label")
                has_snowflake_sentiment = (
                    pd.notna(snowflake_sentiment)
                    and str(snowflake_sentiment).strip() != ""
                )
                if has_snowflake_sentiment:
                    st.metric("Snowflake sentiment", str(snowflake_sentiment))
                    st.caption("Snowflake AI_SENTIMENT")
                    st.write(f"**Risk severity:** {row['sentiment_label']} (deterministic business rule)")
                else:
                    st.metric(
                        "Sentiment",
                        row["sentiment_label"],
                        f"{float(row['sentiment_score']):+.2f}",
                    )
                    st.caption("Deterministic sentiment fallback")
                st.markdown(f"> {row['latest_call_transcript']}")

        with st.container(border=True):
            st.markdown("#### Explainable Risk")
            score_col, explanation_col = st.columns([1, 3])
            with score_col:
                st.metric("Risk score", f"{int(row['risk_score'])}/100")
                st.markdown(
                    risk_badge(row["risk_tier"]),
                    unsafe_allow_html=True,
                )
                st.progress(int(row["risk_score"]))
            with explanation_col:
                contributions = risk_contribution_text(row["risk_explanations"])
                if contributions:
                    for contribution in contributions:
                        st.markdown(f"**{contribution}**")
                else:
                    st.success("No configured risk factor is currently active.")

    with tab_action:
        st.subheader("Retention decision workspace")
        action_name = st.selectbox(
            "Customer for recommendation", names, index=default_index, key="action_customer_name"
        )
        action_row = _selected_row(customer_360, action_name)
        context = customer_context(action_row)
        cache_key = f"{action_name}:{data_source}:{client.working_ai_model}"
        if st.session_state.get("nba_cache_key") != cache_key:
            with st.spinner("Evaluating customer evidence..."):
                ai_client = client if live_data else None
                st.session_state["risk_explanation"] = explain_risk(context, ai_client)
                st.session_state["next_action"] = generate_next_best_action(context, ai_client)
                st.session_state["nba_cache_key"] = cache_key
        explanation = st.session_state["risk_explanation"]
        action = st.session_state["next_action"]

        if action["source"] == "snowflake_ai":
            st.caption("Generated with Snowflake AI_COMPLETE · Grounded in CUSTOMER_360")
        else:
            st.caption("Deterministic fallback")

        with st.container(border=True):
            st.markdown("#### Why is this customer at risk?")
            st.write(explanation["text"])
        with st.container(border=True):
            st.markdown("#### Recommended Next Best Action")
            st.markdown(f"**Priority**  \n{action['priority']}")
            st.markdown(f"**Recommended Action**  \n{action['recommended_action']}")
            st.markdown(f"**Why**  \n{action['why']}")
            st.markdown(f"**Suggested Outreach**  \n> {action['suggested_outreach']}")
            st.markdown(f"**Business Objective**  \n{action['business_objective']}")

    with tab_ask:
        st.subheader("Ask Customer Data")
        if live_data:
            st.caption("Answers grounded in Snowflake CUSTOMER_360")
        else:
            st.caption("Controlled, data-grounded answers from the deterministic local snapshot.")
        suggested = [
            "Which high-value customers are most at risk?",
            "Why is Sarah Khan at risk?",
            "Which customers have unresolved support issues?",
            "Who should the retention team contact first?",
            "Which customers have negative call sentiment?",
        ]
        st.markdown("**Try:** " + " · ".join(suggested))
        with st.form("customer_question_form"):
            question = st.text_input("Question", value=suggested[0])
            submitted = st.form_submit_button("Ask", type="primary")
        if submitted or question:
            result = answer_customer_question(question, customer_360)
            st.markdown(f"#### Answer\n{result['answer']}")
            if result["table"] is not None and not result["table"].empty:
                st.dataframe(result["table"], width="stretch", hide_index=True)

    st.divider()
    st.caption(
        "CustomerPulse AI · Snowflake CoCo CLI Hackathon — GCC Edition · "
        "Challenge 02: Customer 360 & Next Best Action Engine"
    )


if __name__ == "__main__":
    main()
