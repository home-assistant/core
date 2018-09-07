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
from homeassistant.exceptions import PlatformNotReady

REQUIREMENTS = ['bluepy==1.1.4']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Switchmate'
HANDLE = 0x2e
ON_KEY = b'\x00'
OFF_KEY = b'\x01'

SCAN_INTERVAL = timedelta(minutes=30)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MAC): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None) -> None:
    """Perform the setup for Switchmate devices."""
    name = config.get(CONF_NAME)
    mac_addr = config.get(CONF_MAC)
    add_entities([Switchmate(mac_addr, name)], True)


class Switchmate(SwitchDevice):
    """Representation of a Switchmate."""

    def __init__(self, mac, name) -> None:
        """Initialize the Switchmate."""
        # pylint: disable=import-error
        import bluepy
        self._state = False
        self._name = name
        self._mac = mac
        try:
            self._device = bluepy.btle.Peripheral(self._mac,
                                                  bluepy.btle.ADDR_TYPE_RANDOM)
        except bluepy.btle.BTLEException:
            _LOGGER.error("Failed to set up switchmate")
            raise PlatformNotReady()

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
        self._state = self._device.readCharacteristic(HANDLE) == ON_KEY

    @property
    def is_on(self) -> bool:
        """Return true if it is on."""
        return self._state

    def turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        self._device.writeCharacteristic(HANDLE, ON_KEY, True)

    def turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        self._device.writeCharacteristic(HANDLE, OFF_KEY, True)
