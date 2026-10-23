"""Constants for the Livisi Smart Home integration."""

import logging
from typing import Final

from homeassistant.const import TEMPERATURE

LOGGER = logging.getLogger(__package__)
DOMAIN = "livisi"

DEVICE_POLLING_DELAY: Final = 60
WEBSOCKET_RECONNECT_DELAY: Final = 5
LIVISI_STATE_CHANGE: Final = "livisi_state_change"
LIVISI_REACHABILITY_CHANGE: Final = "livisi_reachability_change"

HUMIDITY: Final = "humidity"
IS_OPEN: Final = "isOpen"
ON_STATE: Final = "onState"
POINT_TEMPERATURE: Final = "pointTemperature"
SETPOINT_TEMPERATURE: Final = "setpointTemperature"
STATE_PROPERTIES: Final = (
    HUMIDITY,
    IS_OPEN,
    ON_STATE,
    POINT_TEMPERATURE,
    SETPOINT_TEMPERATURE,
    TEMPERATURE,
)

SWITCH_DEVICE_TYPES: Final = ["ISS", "ISS2", "PSS", "PSSO"]
VRCC_DEVICE_TYPE: Final = "VRCC"
WDS_DEVICE_TYPE: Final = "WDS"


MAX_TEMPERATURE: Final = 30.0
MIN_TEMPERATURE: Final = 6.0
