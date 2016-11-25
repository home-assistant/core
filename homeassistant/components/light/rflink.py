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


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the Rflink platform."""
    entity_device_mapping = {
        'newkaku': DimmableRflinkLight,
    }

    @asyncio.coroutine
    def add_new_device(event):
        """Check if device is known, otherwise add to list of known devices."""
        packet = event.data[rflink.ATTR_PACKET]
        protocol = packet['protocol']
        entity_type = entity_device_mapping.get(protocol, RflinkLight)

        device_id = rflink.serialize_id(packet)
        if device_id not in KNOWN_DEVICE_IDS:
            KNOWN_DEVICE_IDS.append(device_id)
            device = entity_type(device_id, device_id, hass)
            yield from async_add_devices([device])
            # make sure the packet is processed by the new entity
            device.match_packet(packet)

    yield from async_add_devices([
        DimmableRflinkLight('test', 'newkaku_0031095e_c', hass),
    ])

    hass.bus.async_listen(rflink.RFLINK_EVENT[DOMAIN], add_new_device)


class RflinkLight(rflink.RflinkDevice, Light):
    """Representation of a Rflink light."""

    # used for matching bus events
    domain = DOMAIN

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

        self._send_command("turn_on")

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._send_command("turn_off")


class DimmableRflinkLight(RflinkLight):
    """Rflink light device that support dimming."""
    _brightness = 255

    def turn_on(self, **kwargs):
        """Turn the device on."""
        if ATTR_BRIGHTNESS in kwargs:
            # rflink only support 16 brightness levels
            self._brightness = int(kwargs[ATTR_BRIGHTNESS]/16)*16

        self._send_command("dim", self._brightness)

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS
