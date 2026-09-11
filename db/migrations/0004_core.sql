CREATE TABLE core.observation (
    series_id      text NOT NULL REFERENCES meta.series,
    period_start   date NOT NULL,
    period_end     date NOT NULL,
    freq           char(1) NOT NULL,
    value          numeric NOT NULL,
    estimate_stage text,
    vintage_at     timestamptz NOT NULL DEFAULT now(),
    source_run_id  bigint NOT NULL REFERENCES ops.source_run,
    raw_ref        text,
    PRIMARY KEY (series_id, period_start, vintage_at),
    CHECK (period_end >= period_start),
    CHECK (series_id LIKE ('%.' || lower(freq)))
);
COMMENT ON TABLE core.observation IS 'Append-only: a changed value is a new row with a new vintage_at';
COMMENT ON COLUMN core.observation.estimate_stage IS
    'advance_1, advance_2, provisional, revised_1, revised_2, revised_3, final, or NULL';

-- Enforce append-only for every role, owner included. A deliberate correction needs the
-- owner's approval and ALTER TABLE core.observation DISABLE TRIGGER ... (docs/rules.md).
CREATE FUNCTION core.forbid_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'core.observation is append-only (% refused)', TG_OP;
END
$$;

CREATE TRIGGER observation_append_only BEFORE UPDATE OR DELETE ON core.observation
    FOR EACH ROW EXECUTE FUNCTION core.forbid_change();
CREATE TRIGGER observation_no_truncate BEFORE TRUNCATE ON core.observation
    FOR EACH STATEMENT EXECUTE FUNCTION core.forbid_change();

CREATE VIEW core.latest AS
SELECT DISTINCT ON (series_id, period_start) *
FROM core.observation
ORDER BY series_id, period_start, vintage_at DESC;
COMMENT ON VIEW core.latest IS 'Latest vintage per (series_id, period_start)';
