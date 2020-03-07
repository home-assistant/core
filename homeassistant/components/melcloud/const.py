"""Constants for the MELCloud Climate integration."""
import pymelcloud.ata_device as ata_device
from pymelcloud.const import UNIT_TEMP_CELSIUS, UNIT_TEMP_FAHRENHEIT

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
    ata_device.OPERATION_MODE_HEAT: HVAC_MODE_HEAT,
    ata_device.OPERATION_MODE_DRY: HVAC_MODE_DRY,
    ata_device.OPERATION_MODE_COOL: HVAC_MODE_COOL,
    ata_device.OPERATION_MODE_FAN_ONLY: HVAC_MODE_FAN_ONLY,
    ata_device.OPERATION_MODE_HEAT_COOL: HVAC_MODE_HEAT_COOL,
}
HVAC_MODE_REVERSE_LOOKUP = {v: k for k, v in HVAC_MODE_LOOKUP.items()}

TEMP_UNIT_LOOKUP = {
    UNIT_TEMP_CELSIUS: TEMP_CELSIUS,
    UNIT_TEMP_FAHRENHEIT: TEMP_FAHRENHEIT,
}
TEMP_UNIT_REVERSE_LOOKUP = {v: k for k, v in TEMP_UNIT_LOOKUP.items()}
