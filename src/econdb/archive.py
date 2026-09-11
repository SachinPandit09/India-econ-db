"""Raw archive: every downloaded body is gzipped here before it is parsed (docs/rules.md)."""

import gzip
import os
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "data" / "raw"


def root() -> Path:
    return Path(os.environ.get("ECONDB_RAW_DIR") or DEFAULT_ROOT)


def save(relpath: str, body: bytes) -> str:
    """Write body gzipped under the archive root; returns relpath (stored as raw_ref)."""
    path = root() / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(gzip.compress(body))
    tmp.replace(path)
    return relpath


def load(relpath: str) -> bytes:
    return gzip.decompress((root() / relpath).read_bytes())


def files(prefix: str) -> list[str]:
    """Archived files under prefix, oldest first (paths start with the fetch date)."""
    base = root() / prefix
    return (
        sorted(p.relative_to(root()).as_posix() for p in base.rglob("*.json.gz"))
        if base.exists()
        else []
    )
