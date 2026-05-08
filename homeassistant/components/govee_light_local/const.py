"""Constants for the Govee light local integration."""

from datetime import timedelta

DOMAIN = "govee_light_local"
MANUFACTURER = "Govee"

CONF_MULTICAST_ADDRESS_DEFAULT = "239.255.255.250"
CONF_TARGET_PORT_DEFAULT = 4001
CONF_LISTENING_PORT_DEFAULT = 4002
CONF_DISCOVERY_INTERVAL_DEFAULT = 60

SCAN_INTERVAL = timedelta(seconds=30)
# A device is considered unavailable if we have not heard a status response
# from it for three consecutive poll cycles. This tolerates a single dropped
# UDP response plus some jitter before flapping the entity state.
DEVICE_TIMEOUT = SCAN_INTERVAL * 3
DISCOVERY_TIMEOUT = 5
