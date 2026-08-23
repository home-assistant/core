"""Automatically generated file.

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


SUPPORTED_DATABASE_VERSIONS: dict[str, DatabaseVersions] = {
    "mariadb": {
        "supported_lts": ["10.11", "11.4", "11.8", "12.3"],
        "latest_non_lts": "12.2",
    },
    "mysql": {
        "supported_lts": ["8.4", "9.7"],
        "latest_non_lts": "9.6",
    },
}
