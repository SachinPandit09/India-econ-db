-- Five schemas. ops may already exist: the migration runner creates it for ops.schema_migrations.
CREATE SCHEMA meta;
CREATE SCHEMA raw;
CREATE SCHEMA core;
CREATE SCHEMA derived;
CREATE SCHEMA IF NOT EXISTS ops;

COMMENT ON SCHEMA meta IS 'Definitions: sources, catalogue, series, linking factors, release calendar, tracker layout';
COMMENT ON SCHEMA raw IS 'Large source-shaped detail tables (created with their adapters)';
COMMENT ON SCHEMA core IS 'Canonical observations, append-only with vintages';
COMMENT ON SCHEMA derived IS 'Computed aggregates, changes and linked series; rebuilt idempotently';
COMMENT ON SCHEMA ops IS 'Pipeline runs, quality issues, alerts, schema migrations';
