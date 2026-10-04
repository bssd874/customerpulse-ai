USE DATABASE CUSTOMERPULSE_DB;
USE SCHEMA APP;

CREATE TABLE IF NOT EXISTS CUSTOMERS (
    customer_id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    email VARCHAR NOT NULL,
    segment VARCHAR NOT NULL,
    region VARCHAR NOT NULL,
    customer_since DATE NOT NULL,
    product VARCHAR NOT NULL,
    annual_income NUMBER(14, 2) NOT NULL,
    lifetime_value NUMBER(14, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS TRANSACTIONS (
    transaction_id VARCHAR PRIMARY KEY,
    customer_id VARCHAR NOT NULL,
    transaction_date DATE NOT NULL,
    amount NUMBER(14, 2) NOT NULL,
    transaction_type VARCHAR NOT NULL,
    merchant_category VARCHAR NOT NULL,
    status VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS SUPPORT_TICKETS (
    ticket_id VARCHAR PRIMARY KEY,
    customer_id VARCHAR NOT NULL,
    created_at TIMESTAMP_NTZ NOT NULL,
    category VARCHAR NOT NULL,
    priority VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    summary VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS CALL_TRANSCRIPTS (
    call_id VARCHAR PRIMARY KEY,
    customer_id VARCHAR NOT NULL,
    call_date TIMESTAMP_NTZ NOT NULL,
    agent_name VARCHAR NOT NULL,
    transcript VARCHAR NOT NULL
);

