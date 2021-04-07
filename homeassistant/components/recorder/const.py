"""Recorder constants."""

from homeassistant.bootstrap import DATA_INSTANCE  # noqa: F401

SQLITE_URL_PREFIX = "sqlite://"
DOMAIN = "recorder"

CONF_DB_INTEGRITY_CHECK = "db_integrity_check"

# The maximum number of rows (events) we purge in one delete statement
MAX_ROWS_TO_PURGE = 1000
