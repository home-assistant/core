"""Constants for the MELCloud Climate integration."""
import pymelcloud

from homeassistant.components.climate.const import (
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
)
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT

DOMAIN = "melcloud"

HVAC_MODE_LOOKUP = {
    pymelcloud.OPERATION_MODE_HEAT: HVAC_MODE_HEAT,
    pymelcloud.OPERATION_MODE_DRY: HVAC_MODE_DRY,
    pymelcloud.OPERATION_MODE_COOL: HVAC_MODE_COOL,
    pymelcloud.OPERATION_MODE_FAN_ONLY: HVAC_MODE_FAN_ONLY,
    pymelcloud.OPERATION_MODE_HEAT_COOL: HVAC_MODE_HEAT_COOL,
}
HVAC_MODE_REVERSE_LOOKUP = {v: k for k, v in HVAC_MODE_LOOKUP.items()}

TEMP_UNIT_LOOKUP = {
    pymelcloud.UNIT_TEMP_CELSIUS: TEMP_CELSIUS,
    pymelcloud.UNIT_TEMP_FAHRENHEIT: TEMP_FAHRENHEIT,
}
TEMP_UNIT_REVERSE_LOOKUP = {v: k for k, v in TEMP_UNIT_LOOKUP.items()}
