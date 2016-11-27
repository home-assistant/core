"""
Support for Rflink lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.rflink/
"""
import asyncio
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light)
import homeassistant.components.rflink as rflink

from . import DOMAIN

DEPENDENCIES = ['rflink']

_LOGGER = logging.getLogger(__name__)

KNOWN_DEVICE_IDS = []

VALID_CONFIG_KEYS = [
    'aliasses',
    'name',
]


def entity_type_for_device_id(device_id):
    """Return entity class for procotol of a given device_id."""
    entity_type_mapping = {
        'newkaku': 'dimmable',
    }
    protocol = device_id.split('_')[0]
    return entity_type_mapping.get(protocol, None)


def entity_class_for_type(entity_type):
    """Translate entity type to entity class."""
    entity_device_mapping = {
        'dimmable': DimmableRflinkLight,
    }

    return entity_device_mapping.get(entity_type, RflinkLight)


def devices_from_config(domain_config, hass=None):
    """Parse config and add rflink switch devices."""

    devices = []
    for device_id, config in domain_config['devices'].items():
        # extract only valid keys from device configuration
        kwargs = {k: v for k, v in config.items() if k in VALID_CONFIG_KEYS}
        # determine which kind of entity to create
        if 'type' in config:
            entity_type = config['type']
        else:
            entity_type = entity_type_for_device_id(device_id)
        entity_class = entity_class_for_type(entity_type)

        devices.append(entity_class(device_id, hass, **kwargs))

        # now we know
        device_ids = [device_id] + config.get('aliasses', [])
        KNOWN_DEVICE_IDS.extend(device_ids)
    return devices


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the Rflink platform."""
    # add devices from config
    yield from async_add_devices(devices_from_config(config, hass))

    @asyncio.coroutine
    def add_new_device(event):
        """Check if device is known, otherwise add to list of known devices."""
        packet = event.data[rflink.ATTR_PACKET]
        entity_type = entity_type_for_device_id(packet['protocol'])
        entity_class = entity_class_for_type(entity_type)

        device_id = rflink.serialize_id(packet)
        if device_id not in KNOWN_DEVICE_IDS:
            KNOWN_DEVICE_IDS.append(device_id)
            device = entity_class(device_id, hass)
            yield from async_add_devices([device])
            # make sure the packet is processed by the new entity
            device.match_packet(packet)
    hass.bus.async_listen(rflink.RFLINK_EVENT[DOMAIN], add_new_device)


class RflinkLight(rflink.SwitchableRflinkDevice, Light):
    """Representation of a Rflink light."""

    # used for matching bus events
    domain = DOMAIN


class DimmableRflinkLight(RflinkLight):
    """Rflink light device that support dimming."""
    _brightness = 255

    def turn_on(self, **kwargs):
        """Turn the device on."""
        if ATTR_BRIGHTNESS in kwargs:
            # rflink only support 16 brightness levels
            self._brightness = int(kwargs[ATTR_BRIGHTNESS]/17)*17

        # if receiver supports dimming this will turn on the light
        # at the requested dim level
        self._send_command("dim", self._brightness)

        # if the receiving device does not support dimlevel this
        # will ensure it is turned on when full brightness is set
        if self._brightness == 255:
            self._send_command("turn_on")

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS
