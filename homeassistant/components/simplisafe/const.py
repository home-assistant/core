"""Define constants for the SimpliSafe component."""
from datetime import timedelta

DOMAIN = "simplisafe"

ATTR_SERIAL = "serial"

DATA_CLIENT = "client"

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

TOPIC_UPDATE = "update"
