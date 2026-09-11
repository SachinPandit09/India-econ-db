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


def backfill(args: argparse.Namespace) -> int:
    from econdb.runner import backfill

    if not args.stage and not args.dataset:
        raise RuntimeError("give --stage (pilot, A, B, C) and/or --dataset")
    return backfill(args.stage or "all", args.dataset, args.refresh, args.from_archive)


def estimate(args: argparse.Namespace) -> int:
    from econdb.runner import backfill

    return backfill(args.stage or "all", args.dataset, counts_only=True)


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
    for name, func, text in (("backfill", backfill, "full-history load (resumable)"),
                             ("estimate", estimate, "count rows and requests, fetch nothing")):  # fmt: skip
        p = commands.add_parser(name, help=text)
        p.add_argument("--source", choices=["mospi"], required=True)
        p.add_argument("--stage", choices=["pilot", "A", "B", "C"])
        p.add_argument("--dataset", action="append", help="MoSPI dataset, e.g. NAS (repeatable)")
        if name == "backfill":
            p.add_argument(
                "--refresh", action="store_true", help="refetch chunks already completed"
            )
            p.add_argument(
                "--from-archive", action="store_true", help="reload archived pages, no network"
            )
        p.set_defaults(func=func)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (RuntimeError, psycopg.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
