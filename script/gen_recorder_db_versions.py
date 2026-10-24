"""Generate the recorder's supported database versions file from endoflife.date.

Usage:
    python3 -m script.gen_recorder_db_versions            # regenerate the file
    python3 -m script.gen_recorder_db_versions validate   # fail if out of date

For MariaDB and MySQL we track the currently supported (non-end-of-life) LTS
release series and the newest known short-term/innovation release series.

A CI job on the dev branch runs the ``validate`` mode, so it fails whenever a new
(non-patch) MariaDB or MySQL release means the committed file is out of date.

Accessing the network here is a deliberate exception to the general policy of
not doing so in tests/CI; only this maintenance job talks to endoflife.date, and
the recorder itself only reads the committed file. ``validate`` skips (instead of
failing) when endoflife.date cannot be reached, so an outage does not fail
unrelated pull requests.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
import importlib.util
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

SOURCES = {
    "mariadb": "https://endoflife.date/api/mariadb.json",
    "mysql": "https://endoflife.date/api/mysql.json",
}
FETCH_TIMEOUT = 30
FETCH_RETRIES = 3
FETCH_RETRY_WAIT = 2
# Errors that mean we could not get usable data from endoflife.date
FETCH_ERRORS = (urllib.error.URLError, TimeoutError, json.JSONDecodeError)
OUTPUT_FILE = (
    Path(__file__).parent.parent
    / "homeassistant"
    / "generated"
    / "recorder_database_versions.py"
)
HEADER = '''"""Automatically generated file.

To update, run python3 -m script.gen_recorder_db_versions

This file is generated from https://endoflife.date. For each of MariaDB and
MySQL, ``supported_lts`` lists the currently supported (non-end-of-life)
long-term support release series, and ``latest_non_lts`` is the newest known
short-term/innovation release series. Both are ``"<major>.<minor>"`` strings.
"""

from typing import TypedDict


class DatabaseVersions(TypedDict):
    """Supported release series for a database engine."""

    supported_lts: list[str]
    latest_non_lts: str


SUPPORTED_DATABASE_VERSIONS: dict[str, DatabaseVersions] = {'''


def _series_key(cycle: str) -> tuple[int, int]:
    """Return a sortable (major, minor) key for a "<major>.<minor>" cycle."""
    major, _, minor = cycle.partition(".")
    return int(major), int(minor)


def _eol(cycle: dict) -> date:
    """Return the end-of-life date for a cycle (date.max when none is set)."""
    eol = cycle["eol"]
    return date.max if isinstance(eol, bool) else date.fromisoformat(eol)


def _engine_versions(cycles: list[dict], today: date) -> dict:
    """Compute the supported LTS series and latest non-LTS series for an engine."""
    supported_lts = sorted(
        (
            cycle["cycle"]
            for cycle in cycles
            if cycle.get("lts") and _eol(cycle) > today
        ),
        key=_series_key,
    )
    latest_non_lts = max(
        (cycle["cycle"] for cycle in cycles if not cycle.get("lts")),
        key=_series_key,
    )
    return {"supported_lts": supported_lts, "latest_non_lts": latest_non_lts}


def _fetch(url: str) -> list[dict]:
    """Fetch and parse an endoflife.date API response, retrying transient errors."""
    for attempt in range(FETCH_RETRIES):
        try:
            with urllib.request.urlopen(url, timeout=FETCH_TIMEOUT) as response:
                cycles: list[dict] = json.load(response)
                return cycles
        except FETCH_ERRORS:
            if attempt == FETCH_RETRIES - 1:
                raise
            time.sleep(FETCH_RETRY_WAIT)
    raise RuntimeError  # pragma: no cover


def fetch_versions() -> dict:
    """Fetch and compute the supported version data for all engines."""
    today = datetime.now(UTC).date()
    return {
        engine: _engine_versions(_fetch(url), today) for engine, url in SOURCES.items()
    }


def render(versions: dict) -> str:
    """Render the generated recorder_database_versions.py content."""
    lines = [HEADER]
    for engine, data in versions.items():
        supported = ", ".join(f'"{cycle}"' for cycle in data["supported_lts"])
        lines.append(f'    "{engine}": {{')
        lines.append(f'        "supported_lts": [{supported}],')
        lines.append(f'        "latest_non_lts": "{data["latest_non_lts"]}",')
        lines.append("    },")
    lines.append("}")
    return "\n".join(lines) + "\n"


def load_committed() -> dict:
    """Load the committed SUPPORTED_DATABASE_VERSIONS without importing recorder."""
    spec = importlib.util.spec_from_file_location("_database_versions", OUTPUT_FILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    committed: dict = module.SUPPORTED_DATABASE_VERSIONS
    return committed


def main() -> int:
    """Generate the file or validate that the committed one is up to date."""
    if len(sys.argv) > 1 and sys.argv[1] == "validate":
        try:
            versions = fetch_versions()
        except FETCH_ERRORS as err:
            print(f"Skipping validation, could not reach endoflife.date: {err}")
            return 0
        if versions != load_committed():
            relative_path = OUTPUT_FILE.relative_to(Path(__file__).parent.parent)
            print(
                f"{relative_path} is out of date with the latest MariaDB or MySQL "
                "release data from endoflife.date (a new release or an LTS series "
                "reaching end of life).\n"
                "Run: python3 -m script.gen_recorder_db_versions"
            )
            return 1
        return 0
    OUTPUT_FILE.write_text(render(fetch_versions()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
