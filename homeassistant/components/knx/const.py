"""Constants for the KNX integration."""
from enum import Enum
from typing import Final

from homeassistant.components.climate.const import (
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_DRY,
    CURRENT_HVAC_FAN,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    PRESET_SLEEP,
)

DOMAIN: Final = "knx"

# Address is used for configuration and services by the same functions so the key has to match
KNX_ADDRESS: Final = "address"

CONF_INVERT: Final = "invert"
CONF_KNX_EXPOSE: Final = "expose"
CONF_KNX_INDIVIDUAL_ADDRESS: Final = "individual_address"
CONF_KNX_ROUTING: Final = "routing"
CONF_KNX_TUNNELING: Final = "tunneling"
CONF_RESET_AFTER: Final = "reset_after"
CONF_RESPOND_TO_READ: Final = "respond_to_read"
CONF_STATE_ADDRESS: Final = "state_address"
CONF_SYNC_STATE: Final = "sync_state"

ATTR_COUNTER: Final = "counter"
ATTR_LAST_KNX_UPDATE: Final = "last_knx_update"
ATTR_SOURCE: Final = "source"


class ColorTempModes(Enum):
    """Color temperature modes for config validation."""

    ABSOLUTE = "DPT-7.600"
    RELATIVE = "DPT-5.001"


class SupportedPlatforms(Enum):
    """Supported platforms."""

    BINARY_SENSOR = "binary_sensor"
    CLIMATE = "climate"
    COVER = "cover"
    FAN = "fan"
    LIGHT = "light"
    NOTIFY = "notify"
    NUMBER = "number"
    SCENE = "scene"
    SELECT = "select"
    SENSOR = "sensor"
    SWITCH = "switch"
    WEATHER = "weather"


# Map KNX controller modes to HA modes. This list might not be complete.
CONTROLLER_MODES: Final = {
    # Map DPT 20.105 HVAC control modes
    "Auto": HVAC_MODE_AUTO,
    "Heat": HVAC_MODE_HEAT,
    "Cool": HVAC_MODE_COOL,
    "Off": HVAC_MODE_OFF,
    "Fan only": HVAC_MODE_FAN_ONLY,
    "Dry": HVAC_MODE_DRY,
}

CURRENT_HVAC_ACTIONS: Final = {
    "Heat": CURRENT_HVAC_HEAT,
    "Cool": CURRENT_HVAC_COOL,
    "Off": CURRENT_HVAC_OFF,
    "Fan only": CURRENT_HVAC_FAN,
    "Dry": CURRENT_HVAC_DRY,
}

PRESET_MODES: Final = {
    # Map DPT 20.102 HVAC operating modes to HA presets
    "Auto": PRESET_NONE,
    "Frost Protection": PRESET_ECO,
    "Night": PRESET_SLEEP,
    "Standby": PRESET_AWAY,
    "Comfort": PRESET_COMFORT,
}
