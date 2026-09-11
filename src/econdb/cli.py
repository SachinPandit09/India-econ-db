"""Command line: `econdb <command>` or `python -m econdb <command>`."""

import argparse
import sys

import psycopg

from econdb import db


def db_check(args: argparse.Namespace) -> int:
    with db.connect() as conn:
        user, database, version = conn.execute(
            "select current_user, current_database(), current_setting('server_version')"
        ).fetchone()
    print(f"OK: connected as {user} to {database} (PostgreSQL {version})")
    return 0


def migrate(args: argparse.Namespace) -> int:
    from econdb.migrate import migrate

    return migrate(status_only=args.status)


def seed(args: argparse.Namespace) -> int:
    from econdb.seed import seed

    return seed()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="econdb", description="India Economic Database pipeline")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("db-check", help="test the database connection").set_defaults(func=db_check)
    m = commands.add_parser("migrate", help="apply pending db/migrations")
    m.add_argument("--status", action="store_true", help="only list applied and pending files")
    m.set_defaults(func=migrate)
    commands.add_parser(
        "seed", help="load the catalogue and tracker layout into meta"
    ).set_defaults(func=seed)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (RuntimeError, psycopg.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
