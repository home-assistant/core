"""Constants for the Coolmaster integration."""

from homeassistant.components.climate.const import (
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
)

DATA_INFO = "info"
DATA_COORDINATOR = "coordinator"

DOMAIN = "coolmaster"

DEFAULT_PORT = 10102

CONF_SUPPORTED_MODES = "supported_modes"

AVAILABLE_MODES = [
    HVAC_MODE_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_FAN_ONLY,
]
