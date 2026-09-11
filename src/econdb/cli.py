"""Command line: `econdb <command>` or `python -m econdb <command>`."""

import argparse
import sys

import psycopg

from econdb import db

EXPECTED_DATABASE = "econdb"


def db_check() -> int:
    with db.connect() as conn:
        user, database, version = conn.execute(
            "select current_user, current_database(), current_setting('server_version')"
        ).fetchone()
    if database != EXPECTED_DATABASE:
        print(f"error: connected to {database!r}, expected {EXPECTED_DATABASE!r}", file=sys.stderr)
        return 1
    print(f"OK: connected as {user} to {database} (PostgreSQL {version})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="econdb", description="India Economic Database pipeline")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("db-check", help="test the database connection").set_defaults(func=db_check)
    args = parser.parse_args(argv)
    try:
        return args.func()
    except (RuntimeError, psycopg.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
