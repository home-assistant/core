"""
Support for Switchmate.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.switchmate/
"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import SwitchDevice, PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_MAC

REQUIREMENTS = ['pySwitchmate==0.3']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Switchmate'

SCAN_INTERVAL = timedelta(minutes=30)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MAC): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None) -> None:
    """Perform the setup for Switchmate devices."""
    name = config.get(CONF_NAME)
    mac_addr = config[CONF_MAC]
    add_entities([Switchmate(mac_addr, name)], True)


class Switchmate(SwitchDevice):
    """Representation of a Switchmate."""

    def __init__(self, mac, name) -> None:
        """Initialize the Switchmate."""
        import switchmate
        self._name = name
        self._mac = mac
        self._device = switchmate.Switchmate(mac=mac)

    @property
    def unique_id(self) -> str:
        """Return a unique, HASS-friendly identifier for this entity."""
        return self._mac.replace(':', '')

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name

    def update(self) -> None:
        """Synchronize state with switch."""
        self._device.update()

    @property
    def is_on(self) -> bool:
        """Return true if it is on."""
        return self._device.state

    def turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        self._device.turn_on()

    def turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        self._device.turn_off()
