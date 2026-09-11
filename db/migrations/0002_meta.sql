CREATE TABLE meta.source (
    source_id         text PRIMARY KEY,
    name              text NOT NULL,
    tier              text NOT NULL CHECK (tier IN ('T1', 'T1b', 'T2', 'T3', 'T4')),
    base_url          text,
    adapter           text,
    schedule          text,
    expected_lag_days integer,
    active            boolean NOT NULL DEFAULT true,
    notes             text
);
COMMENT ON COLUMN meta.source.schedule IS 'cron expression, Asia/Kolkata';

-- Mirror of the CATALOGUE sheet of docs/reference/India_Econ_Indicator_Catalogue.xlsx
CREATE TABLE meta.catalogue (
    catalogue_id  text PRIMARY KEY,
    theme         text NOT NULL,
    family        text NOT NULL,
    breakdowns    text,
    frequency     text,
    unit          text,
    source_agency text,
    access_method text,
    access_detail text,
    history       text,
    verification  text,
    priority      text CHECK (priority IN ('P1', 'P2', 'P3')),
    build_tier    text,
    notes         text,
    decision      text,
    team_notes    text
);

CREATE TABLE meta.series (
    series_id     text PRIMARY KEY,
    source_id     text NOT NULL REFERENCES meta.source,
    catalogue_id  text REFERENCES meta.catalogue,
    family        text NOT NULL,
    name          text NOT NULL,
    dataset       text,
    dimensions    jsonb NOT NULL DEFAULT '{}',
    unit          text NOT NULL,
    scale         text CHECK (scale IN ('thousand', 'lakh', 'million', 'crore', 'billion')),
    currency      char(3),
    price_basis   text CHECK (price_basis IN ('current', 'constant')),
    seasonal_adj  boolean NOT NULL DEFAULT false,
    freq          char(1) NOT NULL CHECK (freq IN ('D', 'W', 'M', 'Q', 'A', 'O')),
    period_basis  text DEFAULT 'FY' CHECK (period_basis IN ('FY', 'CY', 'AY')),
    base_year     text,
    agg_rule      text NOT NULL
                  CHECK (agg_rule IN ('mean', 'sum', 'end', 'end_mean', 'recompute', 'none')),
    derivation    jsonb,
    source_params jsonb NOT NULL DEFAULT '{}',
    active        boolean NOT NULL DEFAULT true,
    notes         text,
    CHECK (series_id ~ '^[a-z][a-z0-9_]*(\.[a-z0-9_]+){2,}$'),
    CHECK (series_id LIKE ('%.' || lower(freq))),
    CHECK (family = split_part(series_id, '.', 1))
);
COMMENT ON COLUMN meta.series.derivation IS 'NULL = published by the source; otherwise how we compute it (e.g. linked series)';
COMMENT ON COLUMN meta.series.period_basis IS
    'FY Apr-Mar, CY Jan-Dec, AY Jul-Jun (PLFS annual); NULL = explicit periods (survey rounds)';

CREATE TABLE meta.linking_factor (
    family       text NOT NULL,
    scope        text NOT NULL DEFAULT 'all',
    old_base     text NOT NULL,
    new_base     text NOT NULL,
    factor       numeric,
    source_ref   text,
    published_on date,
    notes        text,
    PRIMARY KEY (family, scope, old_base, new_base)
);

CREATE TABLE meta.release_calendar (
    release_id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id        text NOT NULL REFERENCES meta.source,
    dataset          text,
    series_id        text REFERENCES meta.series,
    reference_period date NOT NULL,
    expected_on      date NOT NULL,
    UNIQUE NULLS NOT DISTINCT (source_id, dataset, series_id, reference_period)
);

-- Tracker layout (docs/reference/India_Econ_Tracker_Layout.xlsx): CONTENTS as rows, then columns
CREATE TABLE meta.sheet (
    sheet_code   text PRIMARY KEY CHECK (sheet_code ~ '^[AQMWDO][0-9]{2}$'),
    sheet_name   text NOT NULL UNIQUE,
    position     smallint NOT NULL UNIQUE,
    category     text NOT NULL
                 CHECK (category IN ('Annual', 'Quarterly', 'Monthly', 'Weekly', 'Daily', 'Occasional')),
    title        text NOT NULL,
    blocks       text,
    coverage     text,
    source_text  text,
    access_text  text,
    sheet_type   text NOT NULL CHECK (sheet_type IN ('Official', 'Derived')),
    derived_from text,
    status       text
);

CREATE TABLE meta.sheet_column (
    sheet_code      text NOT NULL REFERENCES meta.sheet,
    column_no       smallint NOT NULL CHECK (column_no > 0),
    block_title     text NOT NULL,
    column_label    text NOT NULL,
    series_id       text REFERENCES meta.series,
    agg             text CHECK (agg IN ('mean', 'sum', 'end', 'max', 'min')),
    transform       text CHECK (transform IN ('yoy_pct', 'stage')),
    calc_kind       text CHECK (calc_kind IN ('pct', 'bps', 'diff')),
    calc_lag        smallint,
    calc_ref_column smallint,
    PRIMARY KEY (sheet_code, column_no),
    CHECK (calc_kind IS NULL OR (series_id IS NULL AND calc_lag > 0 AND calc_ref_column IS NOT NULL))
);
COMMENT ON COLUMN meta.sheet_column.series_id IS 'NULL = formula column, or source not built yet';
COMMENT ON COLUMN meta.sheet_column.agg IS 'How the series is aggregated to the sheet frequency';
COMMENT ON COLUMN meta.sheet_column.calc_kind IS 'Yellow change column, written as a formula in Sheets';
