"""Database access."""

import psycopg

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
