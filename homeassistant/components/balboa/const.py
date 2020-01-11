"""Constants for the Balboa Spa integration."""
from homeassistant.components.climate.const import (
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
)

DOMAIN = "balboa"
BALBOA_PLATFORMS = ["climate"]
CLIMATE_SUPPORTED_MODES = [HVAC_MODE_HEAT, HVAC_MODE_OFF]
CLIMATE_SUPPORTED_FANSTATES = [FAN_OFF, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
