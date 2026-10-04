USE DATABASE CUSTOMERPULSE_DB;
USE SCHEMA APP;

SELECT 'customers' AS dataset, COUNT(*) AS row_count FROM CUSTOMERS
UNION ALL SELECT 'transactions', COUNT(*) FROM TRANSACTIONS
UNION ALL SELECT 'support_tickets', COUNT(*) FROM SUPPORT_TICKETS
UNION ALL SELECT 'call_transcripts', COUNT(*) FROM CALL_TRANSCRIPTS;

SELECT
    name,
    lifetime_value,
    transaction_change_pct,
    recent_failed_transactions,
    unresolved_tickets,
    sentiment_label,
    risk_score,
    risk_tier
FROM CUSTOMER_360
ORDER BY risk_score DESC, lifetime_value DESC;

SELECT * FROM CUSTOMER_360 WHERE name = 'Sarah Khan';

