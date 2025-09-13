"""Constants for the DayBetter light local integration."""

from datetime import timedelta

DOMAIN = "daybetter_light_local"
MANUFACTURER = "DayBetter"

CONF_MULTICAST_ADDRESS_DEFAULT = "255.255.255.255"
CONF_TARGET_PORT_DEFAULT = 6281
CONF_LISTENING_PORT_DEFAULT = 6282
CONF_DISCOVERY_INTERVAL_DEFAULT = 60

SCAN_INTERVAL = timedelta(seconds=30)
DISCOVERY_TIMEOUT = 5
