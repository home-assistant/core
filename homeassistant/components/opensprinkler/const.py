"""Define constants for the opensprinkler component."""

from datetime import timedelta

DOMAIN = "opensprinkler"

CONF_RUN_SECONDS = "run_seconds"

DATA_DEVICES = "devices"

DEFAULT_NAME = "Opensprinkler"
DEFAULT_PORT = 8080
DEFAULT_RUN_SECONDS = 60

SCAN_INTERVAL = timedelta(seconds=5)
