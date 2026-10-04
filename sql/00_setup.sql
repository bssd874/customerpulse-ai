-- Run with a role allowed to create a project database and schema.
-- scripts/setup_snowflake.py falls back to the connection's current namespace
-- when CREATE DATABASE or CREATE SCHEMA is not permitted.
CREATE DATABASE IF NOT EXISTS CUSTOMERPULSE_DB;
CREATE SCHEMA IF NOT EXISTS CUSTOMERPULSE_DB.APP;
USE DATABASE CUSTOMERPULSE_DB;
USE SCHEMA APP;

