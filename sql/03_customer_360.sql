USE DATABASE CUSTOMERPULSE_DB;
USE SCHEMA APP;

CREATE OR REPLACE VIEW CUSTOMER_360 AS
WITH anchor AS (
    SELECT MAX(transaction_date) AS analysis_date FROM TRANSACTIONS
),
transaction_metrics AS (
    SELECT
        t.customer_id,
        COUNT(*) AS total_transactions,
        COUNT_IF(t.status = 'SUCCESS') AS successful_transactions,
        COUNT_IF(t.status IN ('FAILED', 'DECLINED')) AS failed_transactions,
        COUNT_IF(
            t.status IN ('FAILED', 'DECLINED')
            AND t.transaction_date BETWEEN DATEADD(day, -89, a.analysis_date) AND a.analysis_date
        ) AS recent_failed_transactions,
        SUM(IFF(
            t.status = 'SUCCESS'
            AND t.transaction_date BETWEEN DATEADD(day, -89, a.analysis_date) AND a.analysis_date,
            t.amount,
            0
        )) AS recent_transaction_value,
        SUM(IFF(
            t.status = 'SUCCESS'
            AND t.transaction_date BETWEEN DATEADD(day, -179, a.analysis_date) AND DATEADD(day, -90, a.analysis_date),
            t.amount,
            0
        )) AS previous_transaction_value
    FROM TRANSACTIONS t
    CROSS JOIN anchor a
    GROUP BY t.customer_id
),
ticket_metrics AS (
    SELECT
        customer_id,
        COUNT(*) AS total_tickets,
        COUNT_IF(status IN ('OPEN', 'ESCALATED')) AS unresolved_tickets
    FROM SUPPORT_TICKETS
    GROUP BY customer_id
),
latest_ticket AS (
    SELECT customer_id, summary AS latest_ticket_summary
    FROM SUPPORT_TICKETS
    QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY created_at DESC, ticket_id DESC) = 1
),
latest_call AS (
    SELECT customer_id, transcript AS latest_call_transcript
    FROM CALL_TRANSCRIPTS
    QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY call_date DESC, call_id DESC) = 1
),
features AS (
    SELECT
        c.*,
        COALESCE(tx.total_transactions, 0) AS total_transactions,
        COALESCE(tx.successful_transactions, 0) AS successful_transactions,
        COALESCE(tx.failed_transactions, 0) AS failed_transactions,
        COALESCE(tx.recent_failed_transactions, 0) AS recent_failed_transactions,
        COALESCE(tx.recent_transaction_value, 0) AS recent_transaction_value,
        COALESCE(tx.previous_transaction_value, 0) AS previous_transaction_value,
        ROUND(
            CASE
                WHEN COALESCE(tx.previous_transaction_value, 0) > 0
                    THEN (tx.recent_transaction_value - tx.previous_transaction_value)
                         / tx.previous_transaction_value * 100
                WHEN COALESCE(tx.recent_transaction_value, 0) > 0 THEN 100
                ELSE 0
            END,
            1
        ) AS transaction_change_pct,
        COALESCE(tm.total_tickets, 0) AS total_tickets,
        COALESCE(tm.unresolved_tickets, 0) AS unresolved_tickets,
        COALESCE(lt.latest_ticket_summary, 'No support tickets') AS latest_ticket_summary,
        COALESCE(lc.latest_call_transcript, 'No call transcript available') AS latest_call_transcript
    FROM CUSTOMERS c
    LEFT JOIN transaction_metrics tx ON c.customer_id = tx.customer_id
    LEFT JOIN ticket_metrics tm ON c.customer_id = tm.customer_id
    LEFT JOIN latest_ticket lt ON c.customer_id = lt.customer_id
    LEFT JOIN latest_call lc ON c.customer_id = lc.customer_id
),
sentiment AS (
    SELECT
        f.*,
        CASE
            WHEN REGEXP_LIKE(LOWER(latest_call_transcript), '.*(move to another|unacceptable|frustrated.*repeated|frustrated.*still not).*') THEN -0.8
            WHEN REGEXP_LIKE(LOWER(latest_call_transcript), '.*(frustrated|disappointed|declined.*problem|waiting.*issue).*') THEN -0.4
            WHEN REGEXP_LIKE(LOWER(latest_call_transcript), '.*(excellent|satisfied|works well|helpful|appreciate).*') THEN 0.6
            ELSE 0.0
        END AS sentiment_score
    FROM features f
),
scored AS (
    SELECT
        s.*,
        CASE
            WHEN sentiment_score <= -0.55 THEN 'STRONGLY NEGATIVE'
            WHEN sentiment_score <= -0.20 THEN 'NEGATIVE'
            WHEN sentiment_score >= 0.45 THEN 'POSITIVE'
            ELSE 'NEUTRAL'
        END AS sentiment_label,
        IFF(sentiment_score <= -0.55, 30, IFF(sentiment_score <= -0.20, 15, 0)) AS sentiment_points,
        IFF(unresolved_tickets >= 2, 25, IFF(unresolved_tickets = 1, 10, 0)) AS ticket_points,
        IFF(transaction_change_pct <= -40, 25, IFF(transaction_change_pct <= -20, 15, 0)) AS decline_points,
        IFF(recent_failed_transactions >= 2, 20, IFF(recent_failed_transactions = 1, 10, 0)) AS failure_points
    FROM sentiment s
),
final AS (
    SELECT
        scored.*,
        LEAST(100, sentiment_points + ticket_points + decline_points + failure_points) AS risk_score
    FROM scored
)
SELECT
    customer_id,
    name,
    email,
    segment,
    region,
    customer_since,
    product,
    annual_income,
    lifetime_value,
    total_transactions,
    successful_transactions,
    failed_transactions,
    recent_failed_transactions,
    recent_transaction_value,
    previous_transaction_value,
    transaction_change_pct,
    total_tickets,
    unresolved_tickets,
    latest_ticket_summary,
    latest_call_transcript,
    sentiment_score,
    sentiment_label,
    risk_score,
    CASE WHEN risk_score >= 65 THEN 'HIGH' WHEN risk_score >= 35 THEN 'MEDIUM' ELSE 'LOW' END AS risk_tier,
    ARRAY_CONSTRUCT_COMPACT(
        IFF(sentiment_points > 0, OBJECT_CONSTRUCT('points', sentiment_points, 'reason', IFF(sentiment_points = 30, 'Strongly negative call sentiment', 'Moderately negative call sentiment')), NULL),
        IFF(ticket_points > 0, OBJECT_CONSTRUCT('points', ticket_points, 'reason', unresolved_tickets || ' unresolved support ticket' || IFF(unresolved_tickets = 1, '', 's')), NULL),
        IFF(decline_points > 0, OBJECT_CONSTRUCT('points', decline_points, 'reason', 'Transaction value declined ' || ROUND(ABS(transaction_change_pct), 0) || '%'), NULL),
        IFF(failure_points > 0, OBJECT_CONSTRUCT('points', failure_points, 'reason', recent_failed_transactions || ' recent failed transaction' || IFF(recent_failed_transactions = 1, '', 's')), NULL)
    ) AS risk_explanations
FROM final;

-- Optional live-AI enrichment. Setup continues if the role/region lacks AI_SENTIMENT.
CREATE OR REPLACE VIEW CUSTOMER_360_AI AS
SELECT
    c360.*,
    AI_SENTIMENT(c360.latest_call_transcript) AS ai_sentiment
FROM CUSTOMER_360 c360;

