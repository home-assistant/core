"""Constants for the ZhongHong integration."""

from datetime import timedelta
import logging
from typing import Final

from homeassistant.components.climate import FAN_HIGH, FAN_LOW, FAN_MIDDLE

DOMAIN: Final = "zhong_hong"
INTEGRATION_TITLE: Final = "ZhongHong"

LOGGER = logging.getLogger(__package__)

CONF_GATEWAY_ADDRESS: Final = "gateway_address"

FAN_MEDIUM_LOW: Final = "medium_low"
FAN_MEDIUM_HIGH: Final = "medium_high"

ALL_FAN_MODES: Final = [
    FAN_LOW,
    FAN_MEDIUM_LOW,
    FAN_MIDDLE,
    FAN_MEDIUM_HIGH,
    FAN_HIGH,
]

# Home Assistant fan mode → the name the library uses on the wire.
FAN_MODE_MAP: Final = {
    FAN_LOW: "LOW",
    FAN_MEDIUM_LOW: "MIDLOW",
    FAN_MIDDLE: "MID",
    FAN_MEDIUM_HIGH: "MIDHIGH",
    FAN_HIGH: "HIGH",
}
FAN_MODE_REVERSE_MAP: Final = {v: k for k, v in FAN_MODE_MAP.items()}

# A unit acts on a command inside a few seconds and then reports the new state
# unprompted. This is how long to wait before asking for it anyway, to cover
# the reports that never arrive.
READBACK_DELAY: Final = 3

DEFAULT_PORT: Final = 9999
DEFAULT_GATEWAY_ADDRESS: Final = 1

# The gateway pushes state changes, so polling only has to cover pushes that
# were missed while the connection was down.
SCAN_INTERVAL: Final = timedelta(seconds=60)
