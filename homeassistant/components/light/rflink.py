"""Support for Rflink lights.

For more details about this platform, please refer to the documentation
at https://home-assistant.io/components/light.rflink/

"""
import asyncio
import logging

from homeassistant.components import group
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light)
import homeassistant.components.rflink as rflink

from . import DOMAIN

DEPENDENCIES = ['rflink']

_LOGGER = logging.getLogger(__name__)

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
    for device_id, config in domain_config.get('devices', {}).items():
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
        hass.data[rflink.DATA_KNOWN_DEVICES].extend(device_ids)
    return devices


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the Rflink platform."""
    # add devices from config
    yield from async_add_devices(devices_from_config(config, hass))

    # add new (unconfigured) devices to user desired group
    if config.get('new_devices_group'):
        new_devices_group = yield from group.Group.async_create_group(
            hass, config.get('new_devices_group'), [], True)
    else:
        new_devices_group = None

    @asyncio.coroutine
    def add_new_device(ha_event):
        """Check if device is known, otherwise add to list of known devices."""
        event = ha_event.data[rflink.ATTR_EVENT]
        device_id = event['id']

        entity_type = entity_type_for_device_id(event['id'])
        entity_class = entity_class_for_type(entity_type)

        if device_id in hass.data[rflink.DATA_KNOWN_DEVICES]:
            return

        hass.data[rflink.DATA_KNOWN_DEVICES].append(device_id)
        device = entity_class(device_id, hass)
        yield from async_add_devices([device])
        # make sure the event is processed by the new entity
        device.match_event(event)

        # maybe add to new devices group
        if new_devices_group:
            yield from new_devices_group.async_update_tracked_entity_ids(
                list(new_devices_group.tracking) + [device.entity_id])

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
            self._brightness = int(kwargs[ATTR_BRIGHTNESS] / 17) * 17

        # if receiver supports dimming this will turn on the light
        # at the requested dim level
        self._send_command('dim', self._brightness)

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
