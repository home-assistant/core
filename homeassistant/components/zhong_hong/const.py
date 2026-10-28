"""Constants for the ZhongHong integration."""

from datetime import timedelta
import logging
from typing import Final

from homeassistant.components.climate import FAN_HIGH, FAN_LOW, FAN_MIDDLE

DOMAIN: Final = "zhong_hong"
INTEGRATION_TITLE: Final = "ZhongHong"

# When the YAML configuration stops being imported.
BREAKS_IN_HA_VERSION: Final = "2027.3.0"

LOGGER = logging.getLogger(__package__)

CONF_GATEWAY_ADDRESS: Final = "gateway_address"

CONF_FAN_MODES: Final = "fan_modes"

ALL_FAN_MODES: Final = [
    FAN_LOW,
    FAN_MIDDLE,
    FAN_HIGH,
]

# Home Assistant fan mode → the name the library uses on the wire.
FAN_MODE_MAP: Final = {
    FAN_LOW: "LOW",
    FAN_MIDDLE: "MID",
    FAN_HIGH: "HIGH",
}
FAN_MODE_REVERSE_MAP: Final = {v: k for k, v in FAN_MODE_MAP.items()}

DEFAULT_PORT: Final = 9999
DEFAULT_GATEWAY_ADDRESS: Final = 1

# The gateway pushes state changes, so polling only has to cover pushes that
# were missed while the connection was down.
SCAN_INTERVAL: Final = timedelta(seconds=60)
