"""Models for the database in the Recorder."""

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

    # MariaDB can scan all matching rows for large IN lists with DISTINCT,
    # even in versions where MDEV-25020 has been fixed.
    # https://github.com/home-assistant/core/issues/188413
    #
    # PostgreSQL does not support a skip/loose index scan so its
    # also slow for large distinct queries:
    # https://wiki.postgresql.org/wiki/Loose_indexscan
    # https://github.com/home-assistant/core/issues/126084
    slow_range_in_select: bool

    # MySQL 8.x+ can end up with a file-sort on a dependent subquery
    # which makes the query painfully slow.
    # https://github.com/home-assistant/core/issues/137178
    # The solution is to use multiple indexed group-by queries instead
    # of the subquery as long as the group by does not exceed
    # 999 elements since as soon as we hit 1000 elements MySQL
    # will no longer use the group_index_range optimization.
    # https://github.com/home-assistant/core/issues/132865#issuecomment-2543160459
    slow_dependent_subquery: bool
