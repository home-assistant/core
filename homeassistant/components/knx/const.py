"""Constants for the KNX integration."""
from enum import Enum

from homeassistant.components.climate.const import (
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

DOMAIN = "knx"

CONF_INVERT = "invert"
CONF_STATE_ADDRESS = "state_address"
CONF_SYNC_STATE = "sync_state"
CONF_RESET_AFTER = "reset_after"


class ColorTempModes(Enum):
    """Color temperature modes for config validation."""

    absolute = "DPT-7.600"
    relative = "DPT-5.001"


class SupportedPlatforms(Enum):
    """Supported platforms."""

    binary_sensor = "binary_sensor"
    climate = "climate"
    cover = "cover"
    fan = "fan"
    light = "light"
    notify = "notify"
    scene = "scene"
    sensor = "sensor"
    switch = "switch"
    weather = "weather"


# Map KNX controller modes to HA modes. This list might not be complete.
CONTROLLER_MODES = {
    # Map DPT 20.105 HVAC control modes
    "Auto": HVAC_MODE_AUTO,
    "Heat": HVAC_MODE_HEAT,
    "Cool": HVAC_MODE_COOL,
    "Off": HVAC_MODE_OFF,
    "Fan only": HVAC_MODE_FAN_ONLY,
    "Dry": HVAC_MODE_DRY,
}

PRESET_MODES = {
    # Map DPT 20.102 HVAC operating modes to HA presets
    "Auto": PRESET_NONE,
    "Frost Protection": PRESET_ECO,
    "Night": PRESET_SLEEP,
    "Standby": PRESET_AWAY,
    "Comfort": PRESET_COMFORT,
}

ATTR_COUNTER = "counter"
