"""
Support for Rflink lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.rflink/
"""
import asyncio
import logging

import homeassistant.components.rflink as rflink
from homeassistant.components.light import Light

from . import DOMAIN

DEPENDENCIES = ['rflink']

_LOGGER = logging.getLogger(__name__)

# PLATFORM_SCHEMA = rfxtrx.DEFAULT_SCHEMA

KNOWN_DEVICES = []


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the Rflink platform."""

    @asyncio.coroutine
    def add_new_device(event):
        """Check if device is known, otherwise add to list of known devices."""
        packet = event.data[rflink.ATTR_PACKET]
        print(packet)
        device_id = rflink.serialize_id(packet)
        print(device_id)
        if device_id not in KNOWN_DEVICES:
            print('adding')
            KNOWN_DEVICES.append(device_id)
            device = RflinkLight(device_id, device_id, hass)
            yield from async_add_devices([device])
            device._match_packet(packet)
        print(KNOWN_DEVICES)

    print(DOMAIN, rflink.RFLINK_EVENT[DOMAIN])
    hass.bus.async_listen(rflink.RFLINK_EVENT[DOMAIN], add_new_device)


class RflinkLight(rflink.RflinkDevice, Light):
    """Representation of a Rflink light."""

    domain = DOMAIN

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._send_command("turn_on")

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._send_command("turn_off")
