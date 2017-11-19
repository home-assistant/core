"""
Support for ADS switch platform.

For more details about this platform, please refer to the documentation.
https://home-assistant.io/components/switch.ads/

"""
import logging
import voluptuous as vol
from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.components.ads import DATA_ADS, CONF_ADS_VAR
from homeassistant.helpers.entity import ToggleEntity
import homeassistant.helpers.config_validation as cv


_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ['ads']
DEFAULT_NAME = 'ADS Switch'
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADS_VAR): cv.string,
    vol.Optional(CONF_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up switch platform for ADS."""
    ads_hub = hass.data.get(DATA_ADS)

    dev_name = config.get(CONF_NAME)
    ads_var = config.get(CONF_ADS_VAR)

    add_devices([AdsSwitch(ads_hub, dev_name, ads_var)], True)


class AdsSwitch(ToggleEntity):
    """Representation of an Ads switch device."""

    def __init__(self, ads_hub, dev_name, ads_var):
        """Initialize the AdsSwitch entity."""
        self._ads_hub = ads_hub
        self._on_state = False
        self.dev_name = dev_name
        self.ads_var = ads_var

    @property
    def is_on(self):
        """Return if the switch is turned on."""
        return self._on_state

    @property
    def name(self):
        """Return the name of the entity."""
        return self.dev_name

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._ads_hub.write_by_name(self.ads_var, True,
                                    self._ads_hub.PLCTYPE_BOOL)

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._ads_hub.write_by_name(self.ads_var, False,
                                    self._ads_hub.PLCTYPE_BOOL)

    def update(self):
        """Update state of entity."""
        self._on_state = self._ads_hub.read_by_name(
            self.ads_var, self._ads_hub.PLCTYPE_BOOL
        )
