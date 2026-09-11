"""Apply numbered SQL files from db/migrations; record them in ops.schema_migrations."""

import hashlib
from pathlib import Path

from econdb import db

MIGRATIONS = Path(__file__).resolve().parents[2] / "db" / "migrations"

BOOTSTRAP = """
CREATE SCHEMA IF NOT EXISTS ops;
CREATE TABLE IF NOT EXISTS ops.schema_migrations (
    version    text PRIMARY KEY,
    filename   text NOT NULL,
    checksum   text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);
"""


def checksum(path: Path) -> str:
    # git checks out CRLF on Windows and LF on Linux: hash the same text either way
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def pending(files: list[Path], applied: dict[str, str]) -> list[Path]:
    """Files still to apply, in order. Refuses edited applied files and duplicate versions."""
    files = sorted(files)
    versions = [f.name[:4] for f in files]
    if len(set(versions)) != len(versions):
        raise RuntimeError(f"duplicate migration numbers in {MIGRATIONS}")
    for f in files:
        if f.name[:4] in applied and applied[f.name[:4]] != checksum(f):
            raise RuntimeError(f"{f.name} changed after it was applied - add a new migration")
    return [f for f in files if f.name[:4] not in applied]


def migrate(status_only: bool = False) -> int:
    files = sorted(MIGRATIONS.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    with db.connect() as conn:
        conn.autocommit = True  # each migration gets its own transaction below
        conn.execute(BOOTSTRAP)
        applied = dict(conn.execute("SELECT version, checksum FROM ops.schema_migrations"))
        todo = pending(files, applied)
        if status_only:
            for f in files:
                print(f"{'pending' if f in todo else 'applied'}  {f.name}")
            return 0
        for f in todo:
            with conn.transaction():
                conn.execute(f.read_text(encoding="utf-8"))
                conn.execute(
                    "INSERT INTO ops.schema_migrations (version, filename, checksum)"
                    " VALUES (%s, %s, %s)",
                    (f.name[:4], f.name, checksum(f)),
                )
            print(f"applied  {f.name}")
        if not todo:
            print("nothing to apply")
    return 0
