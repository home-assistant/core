"""Recorder constants."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_RESTORED,
    ATTR_SUPPORTED_FEATURES,
    EVENT_RECORDER_5MIN_STATISTICS_GENERATED,  # noqa: F401
    EVENT_RECORDER_HOURLY_STATISTICS_GENERATED,  # noqa: F401
)
from homeassistant.helpers.json import JSON_DUMP  # noqa: F401

if TYPE_CHECKING:
    from .core import Recorder  # noqa: F401


SQLITE_URL_PREFIX = "sqlite://"
MARIADB_URL_PREFIX = "mariadb://"
MARIADB_PYMYSQL_URL_PREFIX = "mariadb+pymysql://"
MYSQLDB_URL_PREFIX = "mysql://"
MYSQLDB_PYMYSQL_URL_PREFIX = "mysql+pymysql://"
DOMAIN = "recorder"

CONF_DB_INTEGRITY_CHECK = "db_integrity_check"

MAX_QUEUE_BACKLOG_MIN_VALUE = 65000
MIN_AVAILABLE_MEMORY_FOR_QUEUE_BACKLOG = 256 * 1024**2

# As soon as we have more than 999 ids, split the query as the
# MySQL optimizer handles it poorly and will no longer
# do an index only scan with a group-by
# https://github.com/home-assistant/core/issues/132865#issuecomment-2543160459
MAX_IDS_FOR_INDEXED_GROUP_BY = 999

# The maximum number of rows (events) we purge in one delete statement

DEFAULT_MAX_BIND_VARS = 4000

DB_WORKER_PREFIX = "DbWorker"

ALL_DOMAIN_EXCLUDE_ATTRS = {ATTR_ATTRIBUTION, ATTR_RESTORED, ATTR_SUPPORTED_FEATURES}

ATTR_KEEP_DAYS = "keep_days"
ATTR_REPACK = "repack"
ATTR_APPLY_FILTER = "apply_filter"

KEEPALIVE_TIME = 30

CONTEXT_ID_AS_BINARY_SCHEMA_VERSION = 36
EVENT_TYPE_IDS_SCHEMA_VERSION = 37
STATES_META_SCHEMA_VERSION = 38
LAST_REPORTED_SCHEMA_VERSION = 43
CIRCULAR_MEAN_SCHEMA_VERSION = 49

LEGACY_STATES_EVENT_ID_INDEX_SCHEMA_VERSION = 28
LEGACY_STATES_EVENT_FOREIGN_KEYS_FIXED_SCHEMA_VERSION = 43
# https://github.com/home-assistant/core/pull/120779
# fixed the foreign keys in the states table but it did
# not bump the schema version which means only databases
# created with schema 44 and later do not need the rebuild.

INTEGRATION_PLATFORM_COMPILE_STATISTICS = "compile_statistics"
INTEGRATION_PLATFORM_LIST_STATISTIC_IDS = "list_statistic_ids"
INTEGRATION_PLATFORM_UPDATE_STATISTICS_ISSUES = "update_statistics_issues"
INTEGRATION_PLATFORM_VALIDATE_STATISTICS = "validate_statistics"

INTEGRATION_PLATFORM_METHODS = {
    INTEGRATION_PLATFORM_COMPILE_STATISTICS,
    INTEGRATION_PLATFORM_LIST_STATISTIC_IDS,
    INTEGRATION_PLATFORM_UPDATE_STATISTICS_ISSUES,
    INTEGRATION_PLATFORM_VALIDATE_STATISTICS,
}


class SupportedDialect(StrEnum):
    """Supported dialects."""

    SQLITE = "sqlite"
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
