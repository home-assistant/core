"""
Component to hold default turn-on values for lights.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/light_defaults/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
DOMAIN = 'light_defaults'

# NOTE: Schema params here were copied from components/light/__init__.py
# They must match the schema of the light turn on service call.

# String representing a profile (built-in ones or external defined).
ATTR_PROFILE = "profile"

COLOR_GROUP = "Color descriptors"

# Lists holding color values
ATTR_RGB_COLOR = "rgb_color"
ATTR_XY_COLOR = "xy_color"
ATTR_HS_COLOR = "hs_color"
ATTR_COLOR_TEMP = "color_temp"
ATTR_KELVIN = "kelvin"
ATTR_COLOR_NAME = "color_name"

# Brightness of the light, 0..255 or percentage
ATTR_BRIGHTNESS = "brightness"
ATTR_BRIGHTNESS_PCT = "brightness_pct"

VALID_BRIGHTNESS = vol.All(vol.Coerce(int), vol.Clamp(min=0, max=255))
VALID_BRIGHTNESS_PCT = vol.All(vol.Coerce(float), vol.Range(min=0, max=100))

LIGHT_VALUES_SCHEMA = vol.Schema({
    vol.Exclusive(ATTR_PROFILE, COLOR_GROUP): cv.string,
    ATTR_BRIGHTNESS: VALID_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT: VALID_BRIGHTNESS_PCT,
    vol.Exclusive(ATTR_COLOR_NAME, COLOR_GROUP): cv.string,
    vol.Exclusive(ATTR_RGB_COLOR, COLOR_GROUP):
        vol.All(vol.ExactSequence((cv.byte, cv.byte, cv.byte)),
                vol.Coerce(tuple)),
    vol.Exclusive(ATTR_XY_COLOR, COLOR_GROUP):
        vol.All(vol.ExactSequence((cv.small_float, cv.small_float)),
                vol.Coerce(tuple)),
    vol.Exclusive(ATTR_HS_COLOR, COLOR_GROUP):
        vol.All(vol.ExactSequence(
            (vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
             vol.All(vol.Coerce(float), vol.Range(min=0, max=100)))),
                vol.Coerce(tuple)),
    vol.Exclusive(ATTR_COLOR_TEMP, COLOR_GROUP):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
    vol.Exclusive(ATTR_KELVIN, COLOR_GROUP):
        vol.All(vol.Coerce(int), vol.Range(min=0)),
})


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: {
        cv.entity_id: LIGHT_VALUES_SCHEMA,
    },
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the default values."""
    hass.data[DOMAIN] = dict()

    for object_id, defaults in config[DOMAIN].items():
        params = dict()
        for key, value in defaults.items():
            params[key] = value
        _LOGGER.debug("Got default turn on params for %s: %s.",
                      object_id, str(params))
        hass.data[DOMAIN][object_id] = params
    return True


def get_light_default(hass, object_id):
    """Get default values for a given light."""
    if DOMAIN not in hass.data or object_id not in hass.data[DOMAIN]:
        return dict()
    return hass.data[DOMAIN][object_id]
