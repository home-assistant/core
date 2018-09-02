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


def setup_platform(hass, config, add_devices, discovery_info=None) -> None:
    """Perform the setup for Switchmate devices."""
    name = config.get(CONF_NAME)
    mac_addr = config.get(CONF_MAC)
    add_devices([Switchmate(mac_addr, name)], True)


class Switchmate(SwitchDevice):
    """Representation of a Switchmate."""

    def __init__(self, mac, name) -> None:
        """Initialize the Switchmate."""
        # pylint: disable=import-error
        import bluepy
        self._state = False
        self._name = name
        self._mac = mac
        self._device = None
        if not self._connect():
            raise PlatformNotReady()
        
    def _connect(self) -> bool:
        import bluepy
        if self._device:
            try:
                self._device.disconnect()
            except bluepy.btle.BTLEException:
                pass
        try:
            self._device = bluepy.btle.Peripheral(self._mac,
                                                  bluepy.btle.ADDR_TYPE_RANDOM)
        except bluepy.btle.BTLEException:
            _LOGGER.error("Failed to connect to switchmate")
            return False
        return True

    def _sendpacket(self, key, retry=2) -> bool:
        import bluepy
        try:
            self._device.writeCharacteristic(HANDLE, key, True)
        except bluepy.btle.BTLEException:
            _LOGGER.error("Cannot connect to switchmate. Retrying")
            if retry < 1:
                return False
            if not self._connect():
                return False
            self._send_packet(retry-1)
        return True

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
        import bluepy
        try:
            self._state = self._device.readCharacteristic(HANDLE) == ON_KEY
        except bluepy.btle.BTLEException:
            self._connect()

    @property
    def is_on(self) -> bool:
        """Return true if it is on."""
        return self._state

    def turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        self._sendpacket(ON_KEY)

    def turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        self._sendpacket(OFF_KEY)
