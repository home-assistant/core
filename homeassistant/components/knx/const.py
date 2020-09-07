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
    PRESET_SLEEP,
)

DOMAIN = "knx"
DATA_KNX = "data_knx"

CONF_STATE_ADDRESS = "state_address"
CONF_SYNC_STATE = "sync_state"


class ColorTempModes(Enum):
    """Color temperature modes for config validation."""

    absolute = "DPT-7.600"
    relative = "DPT-5.001"


class SupportedPlatforms(Enum):
    """Supported platforms."""

    cover = "cover"
    light = "light"
    binary_sensor = "binary_sensor"
    climate = "climate"
    switch = "switch"
    notify = "notify"
    scene = "scene"
    sensor = "sensor"
    weather = "weather"


# Map KNX operation modes to HA modes. This list might not be complete.
OPERATION_MODES = {
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
    "Frost Protection": PRESET_ECO,
    "Night": PRESET_SLEEP,
    "Standby": PRESET_AWAY,
    "Comfort": PRESET_COMFORT,
}
