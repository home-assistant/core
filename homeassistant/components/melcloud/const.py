"""Constants for the MELCloud Climate integration."""
from pymelcloud.const import UNIT_TEMP_CELSIUS, UNIT_TEMP_FAHRENHEIT

from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT

DOMAIN = "melcloud"

ATTR_STATUS = "status"

TEMP_UNIT_LOOKUP = {
    UNIT_TEMP_CELSIUS: TEMP_CELSIUS,
    UNIT_TEMP_FAHRENHEIT: TEMP_FAHRENHEIT,
}
TEMP_UNIT_REVERSE_LOOKUP = {v: k for k, v in TEMP_UNIT_LOOKUP.items()}
