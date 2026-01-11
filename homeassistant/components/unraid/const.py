"""Constants for the Unraid integration."""

from typing import Final

DOMAIN: Final = "unraid"
MANUFACTURER: Final = "Lime Technology"

# Default polling intervals (seconds)
DEFAULT_SYSTEM_POLL_INTERVAL: Final = 30
DEFAULT_STORAGE_POLL_INTERVAL: Final = 300  # 5 minutes

# UPS configuration
CONF_UPS_NOMINAL_POWER: Final = "ups_nominal_power"
DEFAULT_UPS_NOMINAL_POWER: Final = 0  # 0 = disabled, user must set for UPS Power sensor
