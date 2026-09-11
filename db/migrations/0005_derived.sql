-- pop = period over period at the row's freq (daily %, WoW, MoM, QoQ, FY change); yoy = same period last year.
CREATE TABLE derived.observation (
    series_id    text NOT NULL REFERENCES meta.series,
    freq         char(1) NOT NULL CHECK (freq IN ('D', 'W', 'M', 'Q', 'A')),
    period_start date NOT NULL,
    period_end   date NOT NULL,
    method       text NOT NULL CHECK (method IN (
                     'mean', 'sum', 'end', 'max', 'min', 'link',
                     'pop_pct', 'yoy_pct', 'pop_bps', 'yoy_bps', 'pop_diff')),
    value        numeric NOT NULL,
    is_partial   boolean NOT NULL DEFAULT false,
    derived_from text[] NOT NULL,
    computed_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (series_id, freq, method, period_start),
    CHECK (period_end >= period_start)
);
COMMENT ON COLUMN derived.observation.freq IS 'Target frequency (the series may be finer)';
