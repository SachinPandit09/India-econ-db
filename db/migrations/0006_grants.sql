-- Needs the roles from db/bootstrap_roles.sql (run once by the superuser).
-- Pipeline sessions SET ROLE econdb_writer: append-only on raw/core, no DDL, no migrations.
GRANT CONNECT ON DATABASE econdb TO econdb_writer, econdb_reader;
GRANT USAGE ON SCHEMA meta, raw, core, derived, ops TO econdb_writer, econdb_reader;

GRANT SELECT ON ALL TABLES IN SCHEMA meta, raw, core, derived, ops TO econdb_writer, econdb_reader;
GRANT INSERT, UPDATE ON ALL TABLES IN SCHEMA meta TO econdb_writer;
GRANT INSERT ON ALL TABLES IN SCHEMA raw, core TO econdb_writer;
GRANT INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA derived, ops TO econdb_writer;
REVOKE INSERT, UPDATE, DELETE ON ops.schema_migrations FROM econdb_writer;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA meta, ops TO econdb_writer;

-- Same rules for tables created later (e.g. raw.cpi_detail in Phase 2)
ALTER DEFAULT PRIVILEGES FOR ROLE econdb_owner IN SCHEMA meta, raw, core, derived, ops
    GRANT SELECT ON TABLES TO econdb_writer, econdb_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE econdb_owner IN SCHEMA meta
    GRANT INSERT, UPDATE ON TABLES TO econdb_writer;
ALTER DEFAULT PRIVILEGES FOR ROLE econdb_owner IN SCHEMA raw, core
    GRANT INSERT ON TABLES TO econdb_writer;
ALTER DEFAULT PRIVILEGES FOR ROLE econdb_owner IN SCHEMA derived, ops
    GRANT INSERT, UPDATE, DELETE ON TABLES TO econdb_writer;
ALTER DEFAULT PRIVILEGES FOR ROLE econdb_owner IN SCHEMA meta, raw, core, derived, ops
    GRANT USAGE ON SEQUENCES TO econdb_writer;
