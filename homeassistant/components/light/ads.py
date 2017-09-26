"""
Support for ADS light sources.
"""
import logging
import math

import voluptuous as vol

from homeassistant.components.light import Light, ATTR_BRIGHTNESS, \
    SUPPORT_BRIGHTNESS, PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.components.ads import DATA_ADS, PLCTYPE_BOOL, PLCTYPE_UINT
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ['ads']
DEFAULT_NAME = 'ADS Light'
CONF_ADSVAR = 'adsvar'
CONF_ADSVAR_BRIGHTNESS = 'adsvar_brightness'
SUPPORT_ADS = SUPPORT_BRIGHTNESS
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADSVAR): cv.string,
    vol.Optional(CONF_ADSVAR_BRIGHTNESS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    ads_hub = hass.data.get(DATA_ADS)
    if not ads_hub:
        return False

    varname_enable = config.get(CONF_ADSVAR)
    varname_brightness = config.get(CONF_ADSVAR_BRIGHTNESS)
    devname = config.get(CONF_NAME)

    add_devices([AdsLight(ads_hub, varname_enable, varname_brightness,
                          devname)])


class AdsLight(Light):

    def __init__(self, ads_hub, varname_enable, varname_brightness, devname):
        self._ads_hub = ads_hub
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

        self._ads_hub.write_by_name(self.varname_enable, True, PLCTYPE_BOOL)

        if self.varname_brightness is not None:
            self._ads_hub.write_by_name(self.varname_brightness, bval,
                                        PLCTYPE_UINT)

        self._on_state = True

    def turn_off(self, **kwargs):
        """ Turn the light off. """
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is not None:
            self._brightness = brightness
        bval = math.floor(self._brightness / 256.0 * 100.0)
        self._ads_hub.write_by_name(self.varname_brightness, bval,
                                    PLCTYPE_UINT)
        self._ads_hub.write_by_name(self.varname_enable, False,
                                    PLCTYPE_BOOL)
        self._on_state = False

    def value_changed(self, val):
        self._brightness = math.floor(val / 100.0 * 256.0)
        self._on_state = bool(val != 0)
        self.schedule_update_ha_state()
