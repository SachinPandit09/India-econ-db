"""Structured JSON-lines logs in logs/ (ECONDB_LOG_DIR); every line carries the run_id."""

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "logs"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "msg": record.getMessage(),
            **getattr(record, "fields", {}),
        }
        return json.dumps(line, default=str, ensure_ascii=False)


class RunLogger(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        kwargs["extra"] = {"fields": {**self.extra, **kwargs.pop("fields", {})}}
        return msg, kwargs


def setup(run_id: int) -> tuple[RunLogger, Path]:
    """Logger writing JSON lines to logs/econdb-<UTC date>.jsonl; returns (logger, path)."""
    folder = Path(os.environ.get("ECONDB_LOG_DIR") or DEFAULT_DIR)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"econdb-{datetime.now(UTC):%Y-%m-%d}.jsonl"
    logger = logging.getLogger("econdb")
    logger.setLevel(logging.INFO)
    if not any(getattr(h, "baseFilename", None) == str(path) for h in logger.handlers):
        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    return RunLogger(logger, {"run_id": run_id}), path
