-- Full source detail kept out of core, a resumable fetch log, and per-dataset source runs.

CREATE FUNCTION raw.forbid_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '%.% is append-only (% refused)', TG_TABLE_SCHEMA, TG_TABLE_NAME, TG_OP;
END
$$;

-- Every CPI line published by MoSPI (base 2024 Current/Back, 2012 group + item, 2010 group)
CREATE TABLE raw.cpi_detail (
    base_year     text NOT NULL,
    series        text NOT NULL,
    state         text NOT NULL,
    sector        text NOT NULL,          -- '' when the endpoint gives no sector (2012 item indices)
    line          text NOT NULL,          -- hierarchy path of names, e.g. 'Food and beverages > Cereals'
    level         text NOT NULL,          -- division / group / class / sub_class / item / subgroup
    code          text,                   -- official code when published (2024 items)
    period_start  date NOT NULL,          -- month
    index_value   numeric,
    inflation     numeric,
    imputation    text,
    status        text,                   -- F / P (2012, 2010)
    vintage_at    timestamptz NOT NULL DEFAULT now(),
    source_run_id bigint NOT NULL REFERENCES ops.source_run,
    raw_ref       text,
    PRIMARY KEY (base_year, series, state, sector, line, period_start, vintage_at)
);

-- Survey detail with many breakdowns (PLFS, ASI, HCES, NFHS): one row per dims × measure × period
CREATE TABLE raw.mospi_detail (
    dataset       text NOT NULL,
    variant       text NOT NULL,          -- e.g. 'A/AY/1' (PLFS freq/year type/indicator), 'NIC2008'
    dims          jsonb NOT NULL,
    dims_key      text GENERATED ALWAYS AS (md5(dims::text)) STORED,
    measure       text NOT NULL,
    period_start  date NOT NULL,
    period_end    date NOT NULL,
    value         numeric NOT NULL,
    unit          text,
    vintage_at    timestamptz NOT NULL DEFAULT now(),
    source_run_id bigint NOT NULL REFERENCES ops.source_run,
    raw_ref       text,
    PRIMARY KEY (dataset, variant, dims_key, measure, period_start, period_end, vintage_at)
);

CREATE TRIGGER cpi_detail_append_only BEFORE UPDATE OR DELETE ON raw.cpi_detail
    FOR EACH ROW EXECUTE FUNCTION raw.forbid_change();
CREATE TRIGGER cpi_detail_no_truncate BEFORE TRUNCATE ON raw.cpi_detail
    FOR EACH STATEMENT EXECUTE FUNCTION raw.forbid_change();
CREATE TRIGGER mospi_detail_append_only BEFORE UPDATE OR DELETE ON raw.mospi_detail
    FOR EACH ROW EXECUTE FUNCTION raw.forbid_change();
CREATE TRIGGER mospi_detail_no_truncate BEFORE TRUNCATE ON raw.mospi_detail
    FOR EACH STATEMENT EXECUTE FUNCTION raw.forbid_change();

-- Completed fetch chunks: a crashed or interrupted backfill resumes after the last one
CREATE TABLE ops.fetch_chunk (
    source_id     text NOT NULL REFERENCES meta.source,
    dataset       text NOT NULL,
    chunk_key     text NOT NULL,
    total_records integer,
    pages         integer NOT NULL,
    rows_fetched  integer NOT NULL,
    source_run_id bigint REFERENCES ops.source_run,
    completed_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (source_id, dataset, chunk_key)
);

-- The loader stages rows in temp tables; bootstrap.sql revoked TEMPORARY from PUBLIC
GRANT TEMPORARY ON DATABASE econdb TO econdb_writer;

ALTER TABLE ops.source_run ADD COLUMN dataset text;
ALTER TABLE ops.source_run DROP CONSTRAINT source_run_status_check;
ALTER TABLE ops.source_run ADD CONSTRAINT source_run_status_check
    CHECK (status IN ('running', 'ok', 'partial', 'failed', 'skipped', 'paused'));
