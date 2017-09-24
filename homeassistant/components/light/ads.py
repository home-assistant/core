"""
Support for ADS light sources.
"""
import math
import logging
import voluptuous as vol

from homeassistant.components.light import Light, ATTR_BRIGHTNESS, \
    SUPPORT_BRIGHTNESS, PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.components import ads
import homeassistant.helpers.config_validation as cv
import pyads

_LOGGER = logging.getLogger(__name__)

CONF_ADSVAR_ENABLE = 'adsvar_enable'
CONF_ADSVAR_BRIGHTNESS = 'adsvar_brightness'

DEFAULT_NAME = 'ADS Light'
DEPENDENCIES = ['ads']

SUPPORT_ADS = SUPPORT_BRIGHTNESS

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADSVAR_ENABLE): cv.string,
    vol.Optional(CONF_ADSVAR_BRIGHTNESS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    varname_enable = config.get(CONF_ADSVAR_ENABLE)
    varname_brightness = config.get(CONF_ADSVAR_BRIGHTNESS)
    devname = config.get(CONF_NAME)

    add_devices([AdsLight(varname_enable, varname_brightness, devname)])


class AdsLight(ads.AdsDevice, Light):

    def __init__(self, varname_enable, varname_brightness, devname):
        ads.AdsDevice.__init__(self)
        self._on_state = False
        self._brightness = 50
        self._devname = devname
        self.varname_enable = varname_enable
        self.varname_brightness = varname_brightness
        self.stype = 'dimmer'

    @property
    def name(self):
        """ Return the name of the device if any. """
        return self._devname

    @property
    def brightness(self):
        """
        Brightness of the light.

        This method is optional. Removing it indicates to Home Assistant
        that brightness is not supported for this light.

        """
        return self._brightness

    @property
    def is_on(self):
        """ If light is on. """
        return self._on_state

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_ADS

    def turn_on(self, **kwargs):
        """ Turn the light on or set a specific dimmer value. """
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is not None:
            self._brightness = brightness

        bval = math.floor(self._brightness / 256.0 * 100.0)

        self.write_by_name(self.varname_enable, True, pyads.PLCTYPE_BOOL)

        if self.varname_brightness is not None:
            self.write_by_name(self.varname_brightness,
                               bval, pyads.PLCTYPE_UINT)

        self._on_state = True

    def turn_off(self, **kwargs):
        """ Turn the light off. """
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is not None:
            self._brightness = brightness
        bval = math.floor(self._brightness / 256.0 * 100.0)
        self.write_by_name(self.varname_brightness, bval, pyads.PLCTYPE_UINT)
        self.write_by_name(self.varname_enable, False, pyads.PLCTYPE_BOOL)
        self._on_state = False

    def value_changed(self, val):
        self._brightness = math.floor(val / 100.0 * 256.0)
        self._on_state = bool(val != 0)
        self.schedule_update_ha_state()
