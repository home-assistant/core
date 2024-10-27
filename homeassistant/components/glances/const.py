"""Constants for Glances component."""

from datetime import timedelta
import sys

DOMAIN = "glances"
CONF_VERSION = "version"

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 61208
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)

CPU_ICON = f"mdi:cpu-{64 if sys.maxsize > 2**32 else 32}-bit"
