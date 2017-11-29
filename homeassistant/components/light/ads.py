"""
Support for ADS light sources.

For more details about this platform, please refer to the documentation.
https://home-assistant.io/components/light.ads/

"""
import logging
import voluptuous as vol
from homeassistant.components.light import Light, ATTR_BRIGHTNESS, \
    SUPPORT_BRIGHTNESS, PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.components.ads import DATA_ADS, CONF_ADS_VAR, \
    CONF_ADS_VAR_BRIGHTNESS
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ['ads']
DEFAULT_NAME = 'ADS Light'
SUPPORT_ADS = SUPPORT_BRIGHTNESS
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADS_VAR): cv.string,
    vol.Optional(CONF_ADS_VAR_BRIGHTNESS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the light platform for ADS."""
    ads_hub = hass.data.get(DATA_ADS)

    varname_enable = config.get(CONF_ADS_VAR)
    varname_brightness = config.get(CONF_ADS_VAR_BRIGHTNESS)
    name = config.get(CONF_NAME)

    add_devices([AdsLight(ads_hub, varname_enable, varname_brightness,
                          name)], True)


class AdsLight(Light):
    """Representation of ADS light."""

    def __init__(self, ads_hub, varname_enable, varname_brightness, name):
        """Initialize AdsLight entity."""
        self._ads_hub = ads_hub
        self._on_state = False
        self._brightness = 50
        self._name = name
        self.varname_enable = varname_enable
        self.varname_brightness = varname_brightness
        self.stype = 'dimmer'

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def brightness(self):
        """Brightness of the light."""
        return self._brightness

    @property
    def is_on(self):
        """If light is on."""
        return self._on_state

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_ADS

    def turn_on(self, **kwargs):
        """Turn the light on or set a specific dimmer value."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is not None:
            self._brightness = brightness

        self._ads_hub.write_by_name(self.varname_enable, True,
                                    self._ads_hub.PLCTYPE_BOOL)

        if self.varname_brightness is not None:
            self._ads_hub.write_by_name(
                self.varname_brightness, self._brightness,
                self._ads_hub.PLCTYPE_UINT
            )

        self._on_state = True

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self._ads_hub.write_by_name(self.varname_enable, False,
                                    self._ads_hub.PLCTYPE_BOOL)
        self._on_state = False

    def update(self):
        """Update state of entity."""
        self._on_state = self._ads_hub.read_by_name(self.varname_enable,
                                                    self._ads_hub.PLCTYPE_BOOL)
        if self.varname_brightness is not None:
            self._brightness = self._ads_hub.read_by_name(
                self.varname_brightness, self._ads_hub.PLCTYPE_UINT
            )
