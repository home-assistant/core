"""
Support for Rflink lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.rflink/
"""
import asyncio
import logging

import homeassistant.components.rflink as rflink
from homeassistant.components.light import (ATTR_BRIGHTNESS,
                                            SUPPORT_BRIGHTNESS, Light)

from . import DOMAIN

DEPENDENCIES = ['rflink']

_LOGGER = logging.getLogger(__name__)

KNOWN_DEVICE_IDS = []

SUPPORTS = {
    'newkaku': SUPPORT_BRIGHTNESS,
}


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the Rflink platform."""
    @asyncio.coroutine
    def add_new_device(event):
        """Check if device is known, otherwise add to list of known devices."""
        packet = event.data[rflink.ATTR_PACKET]
        device_id = rflink.serialize_id(packet)
        if device_id not in KNOWN_DEVICE_IDS:
            KNOWN_DEVICE_IDS.append(device_id)
            device = RflinkLight(device_id, device_id, hass)
            yield from async_add_devices([device])
            # make sure the packet is processed by the new entity
            device.match_packet(packet)

    hass.bus.async_listen(rflink.RFLINK_EVENT[DOMAIN], add_new_device)


class RflinkLight(rflink.RflinkDevice, Light):
    """Representation of a Rflink light."""

    # used for matching bus events
    domain = DOMAIN
    _brightness = 255

    def _handle_packet(self, packet):
        """Domain specific packet handler."""
        command = packet['command']
        if command == 'on':
            self._state = True
        elif command == 'off':
            self._state = False

    def turn_on(self, **kwargs):
        """Turn the device on."""
        if ATTR_BRIGHTNESS in kwargs:
            # rflink only support 16 brightness levels
            self._brightness = int(kwargs[ATTR_BRIGHTNESS]/16)*16

        supports = self.supported_features
        if supports and supports & SUPPORT_BRIGHTNESS:
            self._send_command("dim", self._brightness)
        else:
            self._send_command("turn_on")

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._send_command("turn_off")

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        protocol = self._device_id.split('_')[0]
        return SUPPORTS.get(protocol, 0)
