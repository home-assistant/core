"""Constants for the Adaptive Lighting integration."""
import voluptuous as vol

from homeassistant.components.light import VALID_TRANSITION
import homeassistant.helpers.config_validation as cv

ICON = "mdi:theme-light-dark"

DOMAIN = "adaptive_lighting"
SUN_EVENT_NOON = "solar_noon"
SUN_EVENT_MIDNIGHT = "solar_midnight"

CONF_NAME, DEFAULT_NAME = "name", "default"
CONF_LIGHTS, DEFAULT_LIGHTS = "lights", []
CONF_DETECT_NON_HA_CHANGES, DEFAULT_DETECT_NON_HA_CHANGES = (
    "detect_non_ha_changes",
    False,
)
CONF_INITIAL_TRANSITION, DEFAULT_INITIAL_TRANSITION = "initial_transition", 1
CONF_INTERVAL, DEFAULT_INTERVAL = "interval", 90
CONF_MAX_BRIGHTNESS, DEFAULT_MAX_BRIGHTNESS = "max_brightness", 100
CONF_MAX_COLOR_TEMP, DEFAULT_MAX_COLOR_TEMP = "max_color_temp", 5500
CONF_MIN_BRIGHTNESS, DEFAULT_MIN_BRIGHTNESS = "min_brightness", 1
CONF_MIN_COLOR_TEMP, DEFAULT_MIN_COLOR_TEMP = "min_color_temp", 2000
CONF_ONLY_ONCE, DEFAULT_ONLY_ONCE = "only_once", False
CONF_PREFER_RGB_COLOR, DEFAULT_PREFER_RGB_COLOR = "prefer_rgb_color", False
CONF_SEPARATE_TURN_ON_COMMANDS, DEFAULT_SEPARATE_TURN_ON_COMMANDS = (
    "separate_turn_on_commands",
    False,
)
CONF_SLEEP_BRIGHTNESS, DEFAULT_SLEEP_BRIGHTNESS = "sleep_brightness", 1
CONF_SLEEP_COLOR_TEMP, DEFAULT_SLEEP_COLOR_TEMP = "sleep_color_temp", 1000
CONF_SUNRISE_OFFSET, DEFAULT_SUNRISE_OFFSET = "sunrise_offset", 0
CONF_SUNRISE_TIME = "sunrise_time"
CONF_SUNSET_OFFSET, DEFAULT_SUNSET_OFFSET = "sunset_offset", 0
CONF_SUNSET_TIME = "sunset_time"
CONF_TAKE_OVER_CONTROL, DEFAULT_TAKE_OVER_CONTROL = "take_over_control", True
CONF_TRANSITION, DEFAULT_TRANSITION = "transition", 45

SLEEP_MODE_SWITCH = "sleep_mode_switch"
ADAPT_COLOR_SWITCH = "adapt_color_switch"
ADAPT_BRIGHTNESS_SWITCH = "adapt_brightness_switch"
ATTR_TURN_ON_OFF_LISTENER = "turn_on_off_listener"
UNDO_UPDATE_LISTENER = "undo_update_listener"
NONE_STR = "None"
ATTR_ADAPT_COLOR = "adapt_color"
ATTR_ADAPT_BRIGHTNESS = "adapt_brightness"

SERVICE_SET_MANUAL_CONTROL = "set_manual_control"
CONF_MANUAL_CONTROL = "manual_control"
SERVICE_APPLY = "apply"
CONF_TURN_ON_LIGHTS = "turn_on_lights"

TURNING_OFF_DELAY = 5


def int_between(min_int, max_int):
    """Return an integer between 'min_int' and 'max_int'."""
    return vol.All(vol.Coerce(int), vol.Range(min=min_int, max=max_int))


VALIDATION_TUPLES = [
    (CONF_LIGHTS, DEFAULT_LIGHTS, cv.entity_ids),
    (CONF_PREFER_RGB_COLOR, DEFAULT_PREFER_RGB_COLOR, bool),
    (CONF_INITIAL_TRANSITION, DEFAULT_INITIAL_TRANSITION, VALID_TRANSITION),
    (CONF_TRANSITION, DEFAULT_TRANSITION, VALID_TRANSITION),
    (CONF_INTERVAL, DEFAULT_INTERVAL, cv.positive_int),
    (CONF_MIN_BRIGHTNESS, DEFAULT_MIN_BRIGHTNESS, int_between(1, 100)),
    (CONF_MAX_BRIGHTNESS, DEFAULT_MAX_BRIGHTNESS, int_between(1, 100)),
    (CONF_MIN_COLOR_TEMP, DEFAULT_MIN_COLOR_TEMP, int_between(1000, 10000)),
    (CONF_MAX_COLOR_TEMP, DEFAULT_MAX_COLOR_TEMP, int_between(1000, 10000)),
    (CONF_SLEEP_BRIGHTNESS, DEFAULT_SLEEP_BRIGHTNESS, int_between(1, 100)),
    (CONF_SLEEP_COLOR_TEMP, DEFAULT_SLEEP_COLOR_TEMP, int_between(1000, 10000)),
    (CONF_SUNRISE_TIME, NONE_STR, str),
    (CONF_SUNRISE_OFFSET, DEFAULT_SUNRISE_OFFSET, int),
    (CONF_SUNSET_TIME, NONE_STR, str),
    (CONF_SUNSET_OFFSET, DEFAULT_SUNSET_OFFSET, int),
    (CONF_ONLY_ONCE, DEFAULT_ONLY_ONCE, bool),
    (CONF_TAKE_OVER_CONTROL, DEFAULT_TAKE_OVER_CONTROL, bool),
    (CONF_DETECT_NON_HA_CHANGES, DEFAULT_DETECT_NON_HA_CHANGES, bool),
    (CONF_SEPARATE_TURN_ON_COMMANDS, DEFAULT_SEPARATE_TURN_ON_COMMANDS, bool),
]


def timedelta_as_int(value):
    """Convert a `datetime.timedelta` object to an integer.

    This integer can be serialized to json but a timedelta cannot.
    """
    return value.total_seconds()


# conf_option: (validator, coerce) tuples
# these validators cannot be serialized but can be serialized when coerced by coerce.
EXTRA_VALIDATION = {
    CONF_INTERVAL: (cv.time_period, timedelta_as_int),
    CONF_SUNRISE_OFFSET: (cv.time_period, timedelta_as_int),
    CONF_SUNRISE_TIME: (cv.time, str),
    CONF_SUNSET_OFFSET: (cv.time_period, timedelta_as_int),
    CONF_SUNSET_TIME: (cv.time, str),
}


def maybe_coerce(key, validation):
    """Coerce the validation into a json serializable type."""
    validation, coerce = EXTRA_VALIDATION.get(key, (validation, None))
    if coerce is not None:
        return vol.All(validation, vol.Coerce(coerce))
    return validation


def replace_none_str(value, replace_with=None):
    """Replace "None" -> replace_with."""
    return value if value != NONE_STR else replace_with


_yaml_validation_tuples = [
    (key, default, maybe_coerce(key, validation))
    for key, default, validation in VALIDATION_TUPLES
] + [(CONF_NAME, DEFAULT_NAME, cv.string)]

_DOMAIN_SCHEMA = vol.Schema(
    {
        vol.Optional(key, default=replace_none_str(default, vol.UNDEFINED)): validation
        for key, default, validation in _yaml_validation_tuples
    }
)
