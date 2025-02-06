"""Models for the database in the Recorder."""

from __future__ import annotations

from dataclasses import dataclass

from awesomeversion import AwesomeVersion

from ..const import SupportedDialect


class UnsupportedDialect(Exception):
    """The dialect or its version is not supported."""


@dataclass
class DatabaseEngine:
    """Properties of the database engine."""

    dialect: SupportedDialect
    optimizer: DatabaseOptimizer
    max_bind_vars: int
    version: AwesomeVersion | None


@dataclass
class DatabaseOptimizer:
    """Properties of the database optimizer for the configured database engine."""

    # Some MariaDB versions have a bug that causes a slow query when using
    # a range in a select statement with an IN clause.
    #
    # https://jira.mariadb.org/browse/MDEV-25020
    #
    # PostgreSQL does not support a skip/loose index scan so its
    # also slow for large distinct queries:
    # https://wiki.postgresql.org/wiki/Loose_indexscan
    # https://github.com/home-assistant/core/issues/126084
    slow_range_in_select: bool
