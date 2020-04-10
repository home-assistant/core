"""Constants for the MELCloud Climate integration."""
from pymelcloud.const import UNIT_TEMP_CELSIUS, UNIT_TEMP_FAHRENHEIT

from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT

DOMAIN = "melcloud"

CONF_POSITION = "position"

ATTR_STATUS = "status"
ATTR_VANE_HORIZONTAL = "vane_horizontal"
ATTR_VANE_HORIZONTAL_POSITIONS = "vane_horizontal_positions"
ATTR_VANE_VERTICAL = "vane_vertical"
ATTR_VANE_VERTICAL_POSITIONS = "vane_vertical_positions"

SERVICE_SET_VANE_HORIZONTAL = "set_vane_horizontal"
SERVICE_SET_VANE_VERTICAL = "set_vane_vertical"

TEMP_UNIT_LOOKUP = {
    UNIT_TEMP_CELSIUS: TEMP_CELSIUS,
    UNIT_TEMP_FAHRENHEIT: TEMP_FAHRENHEIT,
}
TEMP_UNIT_REVERSE_LOOKUP = {v: k for k, v in TEMP_UNIT_LOOKUP.items()}
