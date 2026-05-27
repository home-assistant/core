"""Constants for the ALLNET integration."""

from __future__ import annotations

DOMAIN = "allnet"

CONF_USE_SSL = "use_ssl"
CONF_DEVICE_PROFILE = "device_profile"

DEFAULT_SCAN_INTERVAL = 30
DEFAULT_USE_SSL = False
DEFAULT_DEVICE_PROFILE = "auto"

MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 3600

# mDNS instance-name prefix used by ALLNET MSR devices (e.g. "all3500")
MDNS_INSTANCE_NAME_PREFIX = "all"
