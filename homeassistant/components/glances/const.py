"""Constants for Glances component."""

import sys

DOMAIN = "glances"
CONF_VERSION = "version"

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 61208
DEFAULT_VERSION = 3
DEFAULT_SCAN_INTERVAL = 60

SUPPORTED_VERSIONS = [2, 3]

CPU_ICON = f"mdi:cpu-{64 if sys.maxsize > 2**32 else 32}-bit"
