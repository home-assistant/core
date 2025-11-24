"""Constants for the Duosida EV Charger integration."""

from typing import Final

DOMAIN: Final = "duosida_ev"

# Configuration keys
CONF_DEVICE_ID: Final = "device_id"

# Default values
DEFAULT_PORT: Final = 9988
DEFAULT_SCAN_INTERVAL: Final = 30

# Status codes from conn_status field
STATUS_CODES: Final = {
    0: "Available",
    1: "Preparing",
    2: "Charging",
    3: "Cooling",
    4: "SuspendedEV",
    5: "Finished",
    6: "Holiday",
}
