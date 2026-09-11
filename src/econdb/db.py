"""Database access."""

import psycopg

from econdb import config


def connect() -> psycopg.Connection:
    # DATABASE_URL carries no password; libpq reads PGPASSWORD from the environment.
    return psycopg.connect(config.require("DATABASE_URL"))
