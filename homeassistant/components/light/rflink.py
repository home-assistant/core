"""Support for Rflink lights.

For more details about this platform, please refer to the documentation
at https://home-assistant.io/components/light.rflink/

"""
import asyncio
import logging

from homeassistant.components import group
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light)
from homeassistant.components.rflink import (
    CONF_ALIASSES, CONF_DEVICES, CONF_IGNORE_DEVICES, CONF_NEW_DEVICES_GROUP,
    DATA_DEVICE_REGISTER, DATA_ENTITY_LOOKUP, DATA_KNOWN_DEVICES, DOMAIN,
    EVENT_KEY_COMMAND, EVENT_KEY_ID, SwitchableRflinkDevice, cv, vol)
from homeassistant.const import CONF_NAME, CONF_PLATFORM, CONF_TYPE

DEPENDENCIES = ['rflink']

_LOGGER = logging.getLogger(__name__)

TYPE_DIMMABLE = 'dimmable'


PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): DOMAIN,
    vol.Optional(CONF_NEW_DEVICES_GROUP, default=None): cv.string,
    vol.Optional(CONF_IGNORE_DEVICES): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_DEVICES, default={}): vol.Schema({
        cv.string: {
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_TYPE): vol.Any(TYPE_DIMMABLE),
            vol.Optional(CONF_ALIASSES, default=[]):
                vol.All(cv.ensure_list, [cv.string]),
        },
    }),
})


def entity_type_for_device_id(device_id):
    """Return entity class for procotol of a given device_id.

    Async friendly.

    """
    entity_type_mapping = {
        'newkaku': TYPE_DIMMABLE,
    }
    protocol = device_id.split('_')[0]
    return entity_type_mapping.get(protocol, None)


def entity_class_for_type(entity_type):
    """Translate entity type to entity class.

    Async friendly.

    """
    entity_device_mapping = {
        TYPE_DIMMABLE: DimmableRflinkLight,
    }

    return entity_device_mapping.get(entity_type, RflinkLight)


def devices_from_config(domain_config, hass=None):
    """Parse config and add rflink switch devices."""
    devices = []
    for device_id, config in domain_config[CONF_DEVICES].items():
        # determine which kind of entity to create
        if CONF_TYPE in config:
            entity_type = config.pop(CONF_TYPE)
        else:
            entity_type = entity_type_for_device_id(device_id)
        entity_class = entity_class_for_type(entity_type)

        device = entity_class(device_id, hass, **config)
        devices.append(device)

        # now we know
        device_ids = [device_id] + config[CONF_ALIASSES]
        hass.data[DATA_KNOWN_DEVICES].extend(device_ids)
        # register entity (and aliasses) to listen to incoming rflink events
        for _id in config[CONF_ALIASSES] + [device_id]:
            hass.data[DATA_ENTITY_LOOKUP][
                EVENT_KEY_COMMAND][_id].append(device)

    return devices


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the Rflink platform."""
    # add devices from config
    yield from async_add_devices(devices_from_config(config, hass))

    # add new (unconfigured) devices to user desired group
    if config[CONF_NEW_DEVICES_GROUP]:
        new_devices_group = yield from group.Group.async_create_group(
            hass, config[CONF_NEW_DEVICES_GROUP], [], True)
    else:
        new_devices_group = None

    @asyncio.coroutine
    def add_new_device(event):
        """Check if device is known, otherwise add to list of known devices."""
        device_id = event[EVENT_KEY_ID]

        entity_type = entity_type_for_device_id(event[EVENT_KEY_ID])
        entity_class = entity_class_for_type(entity_type)

        hass.data[DATA_KNOWN_DEVICES].append(device_id)
        device = entity_class(device_id, hass)
        yield from async_add_devices([device])
        # make sure the event is processed by the new entity
        device.handle_event(event)

        # maybe add to new devices group
        if new_devices_group:
            yield from new_devices_group.async_update_tracked_entity_ids(
                list(new_devices_group.tracking) + [device.entity_id])

    hass.data[DATA_DEVICE_REGISTER][EVENT_KEY_COMMAND] = add_new_device


class RflinkLight(SwitchableRflinkDevice, Light):
    """Representation of a Rflink light."""

    pass


class DimmableRflinkLight(SwitchableRflinkDevice, Light):
    """Rflink light device that support dimming."""

    _brightness = 255

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the device on."""
        if ATTR_BRIGHTNESS in kwargs:
            # rflink only support 16 brightness levels
            self._brightness = int(kwargs[ATTR_BRIGHTNESS] / 17) * 17

        # if receiver supports dimming this will turn on the light
        # at the requested dim level
        yield from self._async_send_command('dim', self._brightness)

        # if the receiving device does not support dimlevel this
        # will ensure it is turned on when full brightness is set
        if self._brightness == 255:
            yield from self._async_send_command("turn_on")

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS
