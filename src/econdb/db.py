"""Database access: connection, versioned (upsert-if-changed) loads, run logging."""

import json

import psycopg
from psycopg.types.json import Jsonb

from econdb import config

EXPECTED_DATABASE = "econdb"


def connect() -> psycopg.Connection:
    # DATABASE_URL carries no password; libpq reads PGPASSWORD from the environment.
    conn = psycopg.connect(config.require("DATABASE_URL"))
    dbname = conn.info.dbname
    if dbname != EXPECTED_DATABASE:  # never touch other projects' databases
        conn.close()
        raise RuntimeError(f"connected to {dbname!r}, expected {EXPECTED_DATABASE!r}")
    return conn


# target: (table, temp table, temp columns, match latest vintage (o), changed vs latest (l vs t))
LOADS = {
    "obs": (
        "core.observation",
        "t_obs",
        ["series_id text", "period_start date", "period_end date", "freq char(1)", "value numeric",
         "estimate_stage text", "raw_ref text"],
        "o.series_id = t.series_id AND o.period_start = t.period_start",
        "l.value IS DISTINCT FROM t.value OR l.estimate_stage IS DISTINCT FROM t.estimate_stage",
    ),
    "cpi": (
        "raw.cpi_detail",
        "t_cpi",
        ["base_year text", "series text", "state text", "sector text", "line text", "level text", "code text",
         "period_start date", "index_value numeric", "inflation numeric", "imputation text", "status text",
         "raw_ref text"],
        "o.base_year = t.base_year AND o.series = t.series AND o.state = t.state AND o.sector = t.sector"
        " AND o.line = t.line AND o.period_start = t.period_start",
        "l.index_value IS DISTINCT FROM t.index_value OR l.inflation IS DISTINCT FROM t.inflation"
        " OR l.status IS DISTINCT FROM t.status",
    ),
    "detail": (
        "raw.mospi_detail",
        "t_detail",
        ["dataset text", "variant text", "dims jsonb", "measure text", "period_start date", "period_end date",
         "value numeric", "unit text", "raw_ref text"],
        "o.dataset = t.dataset AND o.variant = t.variant AND o.dims_key = md5(t.dims::text)"
        " AND o.measure = t.measure AND o.period_start = t.period_start AND o.period_end = t.period_end",
        "l.value IS DISTINCT FROM t.value",
    ),
}  # fmt: skip


def load(conn, target: str, rows: list, source_run_id: int) -> tuple[int, int]:
    """Write rule (docs/architecture.md): insert only new keys or values that differ from the latest vintage.

    Returns (rows_new, rows_revised). Re-loading the same rows writes nothing.
    """
    if not rows:
        return 0, 0
    table, temp, columns, match, changed = LOADS[target]
    names = ", ".join(c.split()[0] for c in columns)
    with conn.cursor() as cur:
        cur.execute(f"CREATE TEMP TABLE IF NOT EXISTS {temp} ({', '.join(columns)})")
        cur.execute(f"TRUNCATE {temp}")
        with cur.copy(f"COPY {temp} ({names}) FROM STDIN") as copy:
            for row in rows:
                copy.write_row(
                    [json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else v for v in row]
                )
        cur.execute(
            f"""
            WITH changes AS (
                SELECT t.*, l.vintage_at IS NULL AS is_new
                FROM {temp} t
                LEFT JOIN LATERAL (
                    SELECT o.* FROM {table} o WHERE {match} ORDER BY o.vintage_at DESC LIMIT 1
                ) l ON true
                WHERE l.vintage_at IS NULL OR {changed}
            ), written AS (
                INSERT INTO {table} ({names}, source_run_id) SELECT {names}, %s FROM changes
            )
            SELECT count(*) FILTER (WHERE is_new), count(*) FILTER (WHERE NOT is_new) FROM changes
            """,
            (source_run_id,),
        )
        return cur.fetchone()


SERIES_COLUMNS = ["series_id", "source_id", "catalogue_id", "family", "name", "dataset", "dimensions", "unit",
                  "scale", "currency", "price_basis", "freq", "period_basis", "base_year", "agg_rule",
                  "source_params"]  # fmt: skip


def add_series(conn, rows) -> int:
    """Insert discovered series; existing (e.g. seeded layout) series are never changed."""
    rows = list(rows)
    if not rows:
        return 0
    sql = (
        f"INSERT INTO meta.series ({', '.join(SERIES_COLUMNS)}) VALUES ({', '.join(['%s'] * len(SERIES_COLUMNS))})"
        " ON CONFLICT (series_id) DO NOTHING"
    )
    with conn.cursor() as cur:
        cur.executemany(
            sql,
            [
                [Jsonb(r[c]) if isinstance(r[c], dict) else r[c] for c in SERIES_COLUMNS]
                for r in rows
            ],
        )
        return cur.rowcount


# ---- run logging (ops) ----------------------------------------------------------------------------


def start_run(conn, command: str, triggered_by: str) -> int:
    sql = "INSERT INTO ops.pipeline_run (command, triggered_by, host) VALUES (%s, %s, inet_client_addr()::text) RETURNING run_id"  # noqa: E501
    return conn.execute(sql, (command, triggered_by)).fetchone()[0]


def finish_run(conn, run_id: int, status: str) -> None:
    conn.execute(
        "UPDATE ops.pipeline_run SET status = %s, finished_at = now() WHERE run_id = %s",
        (status, run_id),
    )


def start_source_run(conn, run_id: int, source_id: str, dataset: str) -> int:
    sql = "INSERT INTO ops.source_run (run_id, source_id, dataset) VALUES (%s, %s, %s) RETURNING source_run_id"
    return conn.execute(sql, (run_id, source_id, dataset)).fetchone()[0]


def finish_source_run(
    conn, source_run_id, status, rows_new, rows_revised, latest_period, error=None
) -> None:
    conn.execute(
        "UPDATE ops.source_run SET status = %s, finished_at = now(), rows_new = %s, rows_revised = %s,"
        " latest_period = %s, error = %s WHERE source_run_id = %s",
        (status, rows_new, rows_revised, latest_period, error, source_run_id),
    )


def quality_issue(
    conn, source_run_id, check_name: str, severity: str, detail: dict, series_id=None
) -> None:
    conn.execute(
        "INSERT INTO ops.quality_issue (source_run_id, series_id, check_name, severity, detail)"
        " VALUES (%s, %s, %s, %s, %s)",
        (source_run_id, series_id, check_name, severity, Jsonb(detail)),
    )


def completed_chunks(conn, source_id: str) -> set[str]:
    return {
        r[0]
        for r in conn.execute(
            "SELECT chunk_key FROM ops.fetch_chunk WHERE source_id = %s", (source_id,)
        )
    }


def mark_chunk(
    conn, source_id, dataset, chunk_key, total_records, pages, rows_fetched, source_run_id
) -> None:
    conn.execute(
        "INSERT INTO ops.fetch_chunk (source_id, dataset, chunk_key, total_records, pages, rows_fetched,"
        " source_run_id) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        " ON CONFLICT (source_id, dataset, chunk_key) DO UPDATE SET total_records = EXCLUDED.total_records,"
        " pages = EXCLUDED.pages, rows_fetched = EXCLUDED.rows_fetched, source_run_id = EXCLUDED.source_run_id,"
        " completed_at = now()",
        (source_id, dataset, chunk_key, total_records, pages, rows_fetched, source_run_id),
    )
