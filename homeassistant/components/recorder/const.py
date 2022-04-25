"""Recorder constants."""

from functools import partial
import json
from typing import Final

from homeassistant.const import ATTR_ATTRIBUTION, ATTR_RESTORED, ATTR_SUPPORTED_FEATURES
from homeassistant.helpers.json import JSONEncoder

DATA_INSTANCE = "recorder_instance"
SQLITE_URL_PREFIX = "sqlite://"
DOMAIN = "recorder"

CONF_DB_INTEGRITY_CHECK = "db_integrity_check"

MAX_QUEUE_BACKLOG = 40000

# The maximum number of rows (events) we purge in one delete statement

# sqlite has a limit of 500 when compounding which
# is needed since mariadb cannot optimize away the
# check for a attributes_id existing without
# doing it in a single select
MAX_ROWS_TO_PURGE = 500

DB_WORKER_PREFIX = "DbWorker"

JSON_DUMP: Final = partial(json.dumps, cls=JSONEncoder, separators=(",", ":"))

ALL_DOMAIN_EXCLUDE_ATTRS = {ATTR_ATTRIBUTION, ATTR_RESTORED, ATTR_SUPPORTED_FEATURES}
