"""
Support for Rflink lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.rflink/
"""
import asyncio
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light)

try:
    from homeassistant.components.rflink import (
        CONF_ALIASSES, CONF_AUTOMATIC_ADD, CONF_DEVICE_DEFAULTS, CONF_DEVICES,
        CONF_FIRE_EVENT, CONF_GROUP, CONF_GROUP_ALIASSES, CONF_IGNORE_DEVICES,
        CONF_NOGROUP_ALIASSES, CONF_SIGNAL_REPETITIONS, DATA_DEVICE_REGISTER,
        DATA_ENTITY_GROUP_LOOKUP, DATA_ENTITY_LOOKUP, DEVICE_DEFAULTS_SCHEMA,
        DOMAIN, EVENT_KEY_COMMAND, EVENT_KEY_ID, SwitchableRflinkDevice, cv, vol)
except ImportError as e:
        print(e)

from homeassistant.const import (
    CONF_NAME, CONF_PLATFORM, CONF_TYPE, STATE_UNKNOWN)
from homeassistant.components.cover import CoverDevice

DEPENDENCIES = ['rflink']

_LOGGER = logging.getLogger(__name__)

TYPE_COVER = 'toggle'
TYPE_DOWN = 'roll_down'
TYPE_UP = 'roll_up'
TYPE_STOP = 'roll_stop'

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): DOMAIN,
    vol.Optional(CONF_IGNORE_DEVICES): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_DEVICE_DEFAULTS, default=DEVICE_DEFAULTS_SCHEMA({})):
    DEVICE_DEFAULTS_SCHEMA,
    vol.Optional(CONF_AUTOMATIC_ADD, default=True): cv.boolean,
    vol.Optional(CONF_DEVICES, default={}): vol.Schema({
        cv.string: {
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_TYPE):
                vol.Any(TYPE_COVER),
            vol.Optional(CONF_ALIASSES, default=[]):
                vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_GROUP_ALIASSES, default=[]):
                vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_NOGROUP_ALIASSES, default=[]):
                vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_FIRE_EVENT, default=False): cv.boolean,
            vol.Optional(CONF_SIGNAL_REPETITIONS): vol.Coerce(int),
            vol.Optional(CONF_GROUP, default=True): cv.boolean,
        },
    }),
})


def entity_type_for_device_id(device_id):
    """Return entity class for protocol of a given device_id.

    Async friendly.
    """
    entity_type_mapping = {
        # KlikAanKlikUit support both dimmers and on/off switches on the same
        # protocol
        'RTS': TYPE_COVER,
    }
    protocol = device_id.split('_')[0]
    return entity_type_mapping.get(protocol, None)


def entity_class_for_type(entity_type):
    """Translate entity type to entity class.

    Async friendly.
    """
    entity_device_mapping = {
        # sends only 'up/down' commands for covers which roll down and roll up
        TYPE_COVER: RflinkCover,

    }

    return entity_device_mapping.get(entity_type, RflinkCover)


def devices_from_config(domain_config, hass=None):
    """Parse configuration and add Rflink cover devices."""
    devices = []
    for device_id, config in domain_config[CONF_DEVICES].items():
        # Determine which kind of entity to create
        if CONF_TYPE in config:
            # Remove type from config to not pass it as and argument to entity
            # instantiation
            entity_type = config.pop(CONF_TYPE)
        else:
            entity_type = entity_type_for_device_id(device_id)
        entity_class = entity_class_for_type(entity_type)

        device_config = dict(domain_config[CONF_DEVICE_DEFAULTS], **config)

        #is_hybrid = entity_class is HybridRflinkLight

        # Make user aware this can cause problems
        repetitions_enabled = device_config[CONF_SIGNAL_REPETITIONS] != 1
        #if is_hybrid and repetitions_enabled:
        #    _LOGGER.warning(
        #        "Hybrid type for %s not compatible with signal "
        #        "repetitions. Please set 'dimmable' or 'switchable' "
        #        "type explicity in configuration", device_id)

        device = entity_class(device_id, hass, **device_config)
        devices.append(device)

        # Register entity (and aliasses) to listen to incoming rflink events

        # Device id and normal aliasses respond to normal and group command
        hass.data[DATA_ENTITY_LOOKUP][
            EVENT_KEY_COMMAND][device_id].append(device)
        if config[CONF_GROUP]:
            hass.data[DATA_ENTITY_GROUP_LOOKUP][
                EVENT_KEY_COMMAND][device_id].append(device)
        for _id in config[CONF_ALIASSES]:
            hass.data[DATA_ENTITY_LOOKUP][
                EVENT_KEY_COMMAND][_id].append(device)
            hass.data[DATA_ENTITY_GROUP_LOOKUP][
                EVENT_KEY_COMMAND][_id].append(device)
        # group_aliasses only respond to group commands
        for _id in config[CONF_GROUP_ALIASSES]:
            hass.data[DATA_ENTITY_GROUP_LOOKUP][
                EVENT_KEY_COMMAND][_id].append(device)
        # nogroup_aliasses only respond to normal commands
        for _id in config[CONF_NOGROUP_ALIASSES]:
            hass.data[DATA_ENTITY_LOOKUP][
                EVENT_KEY_COMMAND][_id].append(device)

    return devices


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Rflink cover platform."""
    async_add_devices(devices_from_config(config, hass))

    @asyncio.coroutine
    def add_new_device(event):
        """Check if device is known, otherwise add to list of known devices."""
        device_id = event[EVENT_KEY_ID]

        entity_type = entity_type_for_device_id(event[EVENT_KEY_ID])
        entity_class = entity_class_for_type(entity_type)

        device_config = config[CONF_DEVICE_DEFAULTS]
        device = entity_class(device_id, hass, **device_config)
        async_add_devices([device])

        # Register entity to listen to incoming Rflink events
        hass.data[DATA_ENTITY_LOOKUP][
            EVENT_KEY_COMMAND][device_id].append(device)

        # Schedule task to process event after entity is created
        hass.async_add_job(device.handle_event, event)

    if config[CONF_AUTOMATIC_ADD]:
        hass.data[DATA_DEVICE_REGISTER][EVENT_KEY_COMMAND] = add_new_device

class RflinkCover(SwitchableRflinkDevice, CoverDevice):
    """Representation of a Rflink cover."""

    @property
    def should_poll(self):
        """No polling available in Rflink cover."""
        return False

    # @property
    # def entity_id(self):
    #     """Return entity id."""
    #     return "light.{}".format(self.name)

    def _handle_event(self, event):
        """Adjust state if Rflink picks up a remote command for this device."""
        self.cancel_queued_send_commands()

        command = event['command']
        if command == 'on':
            # if the state is unknown or false, it gets set as true
            # if the state is true, it gets set as false
            self._state = self._state in [STATE_UNKNOWN, False]

    @asyncio.coroutine
    def is_closed(self):
        """Return if the cover is closed."""
        return None

    @asyncio.coroutine
    def open_cover(self, **kwargs):
        """Move the cover up."""
        yield from self._async_handle_command("roll_up")

    @asyncio.coroutine
    def close_cover(self, **kwargs):
        """Move the cover down."""
        yield from self._async_handle_command("roll_down")

    @asyncio.coroutine
    def stop_cover(self, **kwargs):
        """Stop the cover."""
        yield from self._async_handle_command("stop_roll")