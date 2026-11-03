-- Lesson 0: run only in a disposable classroom database as its administrator.
-- Create the database and login role separately. Enter passwords in psql's
-- interactive \password command; never commit a real password into this file.
CREATE SCHEMA IF NOT EXISTS rag_demo;

CREATE TABLE IF NOT EXISTS rag_demo.notes (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject text NOT NULL,
    body text NOT NULL,
    internal_email text
);

INSERT INTO rag_demo.notes (subject, body, internal_email) VALUES
    ('Refunds', 'Customers can request a refund within 30 days of purchase. Proof of purchase is required.', 'private@example.invalid'),
    ('Onboarding', 'New accounts complete identity verification before activation. Support reviews missing documents.', 'private@example.invalid'),
    ('Billing support', 'Duplicate charges are investigated by the billing team. Verified duplicates are refunded.', 'private@example.invalid');

-- A named non-superuser, non-owner login role rag_reader must already exist.
GRANT USAGE ON SCHEMA rag_demo TO rag_reader;
GRANT SELECT (id, subject, body) ON rag_demo.notes TO rag_reader;
ALTER ROLE rag_reader SET default_transaction_read_only = on;
ALTER ROLE rag_reader SET statement_timeout = '10s';

-- Do not grant SELECT on internal_email, schema CREATE, or role membership.
-- Review inherited PUBLIC privileges and executable functions in a dedicated
-- database before deployment; PostgreSQL grants some PUBLIC rights by default.