"""
Support for ADS switch platform.

For more details about this platform, please refer to the documentation.
https://home-assistant.io/components/switch.ads/
"""
import logging

import voluptuous as vol

from homeassistant.components.ads import CONF_ADS_VAR, DATA_ADS
from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import ToggleEntity

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['ads']

DEFAULT_NAME = 'ADS Switch'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADS_VAR): cv.string,
    vol.Optional(CONF_NAME): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up switch platform for ADS."""
    ads_hub = hass.data.get(DATA_ADS)

    name = config.get(CONF_NAME)
    ads_var = config.get(CONF_ADS_VAR)

    add_entities([AdsSwitch(ads_hub, name, ads_var)], True)


class AdsSwitch(ToggleEntity):
    """Representation of an Ads switch device."""

    def __init__(self, ads_hub, name, ads_var):
        """Initialize the AdsSwitch entity."""
        self._ads_hub = ads_hub
        self._on_state = False
        self._name = name
        self.ads_var = ads_var

    async def async_added_to_hass(self):
        """Register device notification."""
        def update(name, value):
            """Handle device notification."""
            _LOGGER.debug('Variable %s changed its value to %d', name, value)
            self._on_state = value
            self.schedule_update_ha_state()

        self.hass.async_add_job(
            self._ads_hub.add_device_notification,
            self.ads_var, self._ads_hub.PLCTYPE_BOOL, update)

    @property
    def is_on(self):
        """Return if the switch is turned on."""
        return self._on_state

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def should_poll(self):
        """Return False because entity pushes its state to HA."""
        return False

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._ads_hub.write_by_name(
            self.ads_var, True, self._ads_hub.PLCTYPE_BOOL)

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._ads_hub.write_by_name(
            self.ads_var, False, self._ads_hub.PLCTYPE_BOOL)
