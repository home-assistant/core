"""
Support for Switchbot.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.switchbot
"""
import binascii
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import SwitchDevice, PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_MAC

REQUIREMENTS = ['bluepy==1.1.4']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Switchbot'
UUID = "cba20d00-224d-11e6-9fb8-0002a5d5c51b"
HANDLE = "cba20002-224d-11e6-9fb8-0002a5d5c51b"
ON_KEY = "570101"
OFF_KEY = "570102"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MAC): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Perform the setup for Switchbot devices."""
    name = config.get(CONF_NAME)
    mac_addr = config.get(CONF_MAC)
    add_devices([SwitchBot(mac_addr, name)])


class SwitchBot(SwitchDevice):
    """Representation of a Switchbot."""

    def __init__(self, mac, name) -> None:
        """Initialize the Switchbot."""
        self._state = False
        self._name = name
        self._mac = mac
        self._device = None

    def _sendpacket(self, key, retry=2) -> bool:
        import bluepy
        try:
            device = bluepy.btle.Peripheral(self._mac,bluepy.btle.ADDR_TYPE_RANDOM)
            hand_service = device.getServiceByUUID(UUID)
            hand = hand_service.getCharacteristics(HANDLE)[0]
            hand.write(binascii.a2b_hex(key))
            device.disconnect()
        except bluepy.btle.BTLEException:
            _LOGGER.error("Cannot connect to switchbot.", exc_info=True)
            if retry < 1:
                return False
            self._sendpacket(key, retry-1)
        return True

    def turn_on(self, **kwargs) -> None:
        """Turn device on."""
        if self._sendpacket(ON_KEY):
            self._state = True

    def turn_off(self, **kwargs) -> None:
        """Turn device off."""
        if self._sendpacket(OFF_KEY):
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
