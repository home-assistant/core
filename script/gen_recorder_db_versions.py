"""Generate the recorder's supported database versions file from endoflife.date.

Usage:
    python3 -m script.gen_recorder_db_versions            # regenerate the file
    python3 -m script.gen_recorder_db_versions validate   # fail if out of date

For MariaDB and MySQL we track the currently supported (non-end-of-life) LTS
release series and the newest known short-term/innovation release series. A CI
job on the dev branch runs the ``validate`` mode, so it fails whenever a new
(non-patch) MariaDB or MySQL release means the committed file is out of date.

Accessing the network here is a deliberate exception to the general policy of
not doing so in tests/CI; only this maintenance job talks to endoflife.date, and
the recorder itself only reads the committed file.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
import importlib.util
import json
from pathlib import Path
import sys
import urllib.request

SOURCES = {
    "mariadb": "https://endoflife.date/api/mariadb.json",
    "mysql": "https://endoflife.date/api/mysql.json",
}
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


def _engine_versions(cycles: list[dict]) -> dict:
    """Compute the supported LTS series and latest non-LTS series for an engine."""
    today = datetime.now(UTC).date()
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


def fetch_versions() -> dict:
    """Fetch and compute the supported version data for all engines."""
    versions = {}
    for engine, url in SOURCES.items():
        with urllib.request.urlopen(url) as response:
            cycles = json.load(response)
        versions[engine] = _engine_versions(cycles)
    return versions


def render(versions: dict) -> str:
    """Render the generated database_versions.py content."""
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
    validate = len(sys.argv) > 1 and sys.argv[1] == "validate"
    versions = fetch_versions()
    if validate:
        if versions != load_committed():
            print(
                "homeassistant/components/recorder/database_versions.py is out of "
                "date with a new MariaDB or MySQL release.\n"
                "Run: python3 -m script.gen_recorder_db_versions"
            )
            return 1
        return 0
    OUTPUT_FILE.write_text(render(versions))
    return 0


if __name__ == "__main__":
    sys.exit(main())
