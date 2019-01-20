"""
Use SDCP network control to power on/off and check state of Sony projector.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/switch.sony_projector/
"""
import logging

import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    STATE_ON, STATE_OFF, CONF_NAME, CONF_HOST)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pysdcp==1']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Sony Projector'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Connect to Sony projector using network"""
    host = config[CONF_HOST]
    name = config.get(CONF_NAME)

    add_entities([SonyProjector(host, name)], True)


class SonyProjector(SwitchDevice):
    """Represents a Sony Projector as a switch."""

    def __init__(self, host, name):
        """Init of the Sony projector."""
        import pysdcp
        self._sdcp = pysdcp.Projector(host)
        self._name = name
        self._host = host
        self._state = None
        self._available = False
        self._attributes = {}

    @property
    def available(self):
        """Return if projector is available."""
        return self._available

    @property
    def name(self):
        """Return name of the projector."""
        return self._name

    @property
    def is_on(self):
        """Return if the projector is turned on."""
        return self._state

    @property
    def state_attributes(self):
        """Return state attributes."""
        return self._attributes

    def update(self):
        """Get the latest state from the projector."""
        try:
            self._state = self._sdcp.get_power()
            self._available = True
        except ConnectionRefusedError:
            _LOGGER.error("Projector connection refused")
            self._available = False

    def turn_on(self, **kwargs):
        """Turn the projector on."""
        _LOGGER.debug("Powering on projector at %s...", self._host)
        if self._sdcp.set_power(True):
            _LOGGER.debug("Powered on successfully.")
            self._state = STATE_ON
        else:
            _LOGGER.warning("Power on command was not successful")

    def turn_off(self, **kwargs):
        """Turn the projector off."""
        _LOGGER.debug("Powering off projector at %s...", self._host)
        if self._sdcp.set_power(False):
            _LOGGER.debug("Powered off successfully.")
            self._state = STATE_OFF
        else:
            _LOGGER.warning("Power off command was not successful")
