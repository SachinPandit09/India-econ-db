"""Settings from environment variables: `.env` locally, systemd EnvironmentFile on the VPS."""

import os

from dotenv import load_dotenv

load_dotenv()  # finds the repo's .env; never overrides variables already set


def require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set - copy .env.example to .env and fill it in")
    return value
