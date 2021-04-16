"""Recorder constants."""

DATA_INSTANCE = "recorder_instance"
SQLITE_URL_PREFIX = "sqlite://"
DOMAIN = "recorder"

CONF_DB_INTEGRITY_CHECK = "db_integrity_check"

# The maximum number of rows (events) we purge in one delete statement
MAX_ROWS_TO_PURGE = 1000
