"""Constants for the Color helper."""

from typing import Final

DOMAIN: Final = "color"

CONF_INITIAL_BRIGHTNESS: Final = "initial_brightness"
CONF_INITIAL_COLOR: Final = "initial_color"
CONF_INITIAL_KELVIN: Final = "initial_kelvin"
CONF_INITIAL_MODE: Final = "initial_mode"

MODE_CHROMATIC: Final = "chromatic"
MODE_WHITE: Final = "white"

# Internal "kind" of the stored color — chromatic (selected as a color) vs
# white (selected as a color temperature).
KIND_CHROMATIC: Final = "chromatic"
KIND_WHITE: Final = "white"

ATTR_BRIGHTNESS: Final = "brightness"
ATTR_COLOR_TEMP_KELVIN: Final = "color_temp_kelvin"
ATTR_HEX_COLOR: Final = "hex_color"
ATTR_HS_COLOR: Final = "hs_color"
ATTR_KIND: Final = "kind"
ATTR_RGB_COLOR: Final = "rgb_color"
ATTR_XY_COLOR: Final = "xy_color"
# Dict splattable directly into a light.turn_on call: {"xy_color": [x, y]}
# for chromatic, {"color_temp_kelvin": k} for white, plus "brightness" when
# one is stored.
ATTR_COLOR_PARAMS: Final = "color_params"

SERVICE_CLEAR_BRIGHTNESS: Final = "clear_brightness"
SERVICE_SET_BRIGHTNESS: Final = "set_brightness"
SERVICE_SET_COLOR: Final = "set_color"

FIELD_BRIGHTNESS: Final = "brightness"
FIELD_COLOR_NAME: Final = "color_name"
FIELD_HEX: Final = "hex_value"
FIELD_HS: Final = "hs_color"
FIELD_KELVIN: Final = "color_temp_kelvin"
FIELD_RGB: Final = "rgb_color"
FIELD_XY: Final = "xy_color"

DEFAULT_HEX: Final = "#FFFFFF"
DEFAULT_RGB: Final = [255, 255, 255]
DEFAULT_KELVIN: Final = 4000

# Kelvin range accepted on input. Targets clamp to their own min/max.
MIN_KELVIN: Final = 1000
MAX_KELVIN: Final = 20000

# Version 2 added source_field/source_value (the exact user input); version 1
# payloads carried source_hex instead and are migrated on restore.
STATE_SCHEMA_VERSION: Final = 2
