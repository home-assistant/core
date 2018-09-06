"""
Support for Switchbot.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.switchbot
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import SwitchDevice, PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_MAC

REQUIREMENTS = ['PySwitchbot==0.3']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Switchbot'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MAC): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Perform the setup for Switchbot devices."""
    name = config.get(CONF_NAME)
    mac_addr = config[CONF_MAC]
    add_entities([SwitchBot(mac_addr, name)])


class SwitchBot(SwitchDevice):
    """Representation of a Switchbot."""

    def __init__(self, mac, name) -> None:
        """Initialize the Switchbot."""
        import switchbot
        self._state = False
        self._name = name
        self._mac = mac
        self._device = switchbot.Switchbot(mac=mac)

    def turn_on(self, **kwargs) -> None:
        """Turn device on."""
        if self._device.turn_on():
            self._state = True

    def turn_off(self, **kwargs) -> None:
        """Turn device off."""
        if self._device.turn_off():
            self._state = False

    @property
    def assumed_state(self) -> bool:
        """Return true if unable to access real state of entity."""
        return True

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._state

    @property
    def unique_id(self) -> str:
        """Return a unique, HASS-friendly identifier for this entity."""
        return self._mac.replace(':', '')

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name
