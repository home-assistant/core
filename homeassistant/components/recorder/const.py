"""Recorder constants."""

DATA_INSTANCE = "recorder_instance"
SQLITE_URL_PREFIX = "sqlite://"
DOMAIN = "recorder"

CONF_AUTO_PURGE = "auto_purge"
CONF_COMMIT_INTERVAL = "commit_interval"
CONF_DB_URL = "db_url"
CONF_DB_MAX_RETRIES = "db_max_retries"
CONF_DB_RETRY_WAIT = "db_retry_wait"
CONF_DB_INTEGRITY_CHECK = "db_integrity_check"
CONF_PURGE_KEEP_DAYS = "purge_keep_days"

MAX_QUEUE_BACKLOG = 30000

# The maximum number of rows (events) we purge in one delete statement

# sqlite3 has a limit of 999 until version 3.32.0
# in https://github.com/sqlite/sqlite/commit/efdba1a8b3c6c967e7fae9c1989c40d420ce64cc
# We can increase this back to 1000 once most
# have upgraded their sqlite version
MAX_ROWS_TO_PURGE = 998
