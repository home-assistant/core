"""Constants for the iperf3 integration."""

from datetime import timedelta

DOMAIN = "iperf3"
DATA_UPDATED = f"{DOMAIN}_data_updated"

CONF_DURATION = "duration"
CONF_MANUAL = "manual"

DEFAULT_DURATION = 10
DEFAULT_PORT = 5201
DEFAULT_PARALLEL = 1
DEFAULT_PROTOCOL = "tcp"
DEFAULT_INTERVAL = timedelta(minutes=60)

ATTR_DOWNLOAD = "download"
ATTR_UPLOAD = "upload"
ATTR_VERSION = "Version"
ATTR_HOST = "host"

PROTOCOLS = ["tcp", "udp"]
