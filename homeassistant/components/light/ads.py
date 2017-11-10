"""Support for ADS light sources."""

import logging
import math

import voluptuous as vol

from homeassistant.components.light import Light, ATTR_BRIGHTNESS, \
    SUPPORT_BRIGHTNESS, PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.components.ads import DATA_ADS, CONF_ADSVAR
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ['ads']
DEFAULT_NAME = 'ADS Light'
CONF_ADSVAR_BRIGHTNESS = 'adsvar_brightness'
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADSVAR): cv.string,
    vol.Optional(CONF_ADSVAR_BRIGHTNESS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the light platform for ADS."""
    ads_hub = hass.data.get(DATA_ADS)
    if not ads_hub:
        return False

    varname_enable = config.get(CONF_ADSVAR)
    varname_brightness = config.get(CONF_ADSVAR_BRIGHTNESS)
    devname = config.get(CONF_NAME)

    add_devices([AdsLight(ads_hub, varname_enable, varname_brightness,
                          devname)], True)


class AdsLight(Light):
    """Representation of ADS light."""

    def __init__(self, ads_hub, varname_enable, varname_brightness, devname):
        """Initialize AdsLight entity."""
        self._ads_hub = ads_hub
        self._on_state = None
        self._brightness = 255
        self._devname = devname
        self.varname_enable = varname_enable
        self.varname_brightness = varname_brightness

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._devname

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def is_on(self):
        """If light is on."""
        return self._on_state

    @property
    def supported_features(self):
        """Flag supported features."""
        if self.varname_brightness is not None:
            return SUPPORT_BRIGHTNESS  

    def turn_on(self, **kwargs):
        """Turn the light on or set a specific dimmer value."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is not None:
            self._brightness = brightness

        bval = math.floor(self._brightness)

        self._ads_hub.write_by_name(self.varname_enable, True,
                                    self._ads_hub.PLCTYPE_BOOL)

        if self.varname_brightness is not None:
            self._ads_hub.write_by_name(self.varname_brightness, bval,
                                        self._ads_hub.PLCTYPE_UINT)

        self._on_state = True

    def turn_off(self, **kwargs):
        """Turn the light off."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is not None:
            self._brightness = brightness
        bval = math.floor(self._brightness)
        self._ads_hub.write_by_name(self.varname_enable, False,
                                    self._ads_hub.PLCTYPE_BOOL)
        if self.varname_brightness is not None:
            self._ads_hub.write_by_name(self.varname_brightness, bval,
                                        self._ads_hub.PLCTYPE_UINT)
        self._on_state = False

    def value_changed(self, val):
        """Handle value change."""
        self._brightness = val
        self._on_state = bool(val != 0)
        self.schedule_update_ha_state()

    def update(self):
        """Update state of entity."""
        self._on_state = self._ads_hub.read_by_name(self.varname_enable,
                                                    self._ads_hub.PLCTYPE_BOOL)
        if self.varname_brightness is not None:
            self._brightness = self._ads_hub.read_by_name(
                self.varname_brightness, self._ads_hub.PLCTYPE_UINT
            )
