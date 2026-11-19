-- Executado só na criação do volume. Mudou? docker compose down -v
CREATE DATABASE airflow;
CREATE DATABASE urbancare;
\connect urbancare
CREATE SCHEMA IF NOT EXISTS gold;
