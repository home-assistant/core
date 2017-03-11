"""
Support for Rflink lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.rflink/
"""
import asyncio
import logging

from homeassistant.components import group
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light)
from homeassistant.components.rflink import (
    CONF_ALIASSES, CONF_DEVICE_DEFAULTS, CONF_DEVICES, CONF_FIRE_EVENT,
    CONF_IGNORE_DEVICES, CONF_NEW_DEVICES_GROUP, CONF_SIGNAL_REPETITIONS,
    DATA_DEVICE_REGISTER, DATA_ENTITY_LOOKUP, DEVICE_DEFAULTS_SCHEMA, DOMAIN,
    EVENT_KEY_COMMAND, EVENT_KEY_ID, SwitchableRflinkDevice, cv, vol)
from homeassistant.const import CONF_NAME, CONF_PLATFORM, CONF_TYPE

DEPENDENCIES = ['rflink']

_LOGGER = logging.getLogger(__name__)

TYPE_DIMMABLE = 'dimmable'
TYPE_SWITCHABLE = 'switchable'
TYPE_HYBRID = 'hybrid'

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): DOMAIN,
    vol.Optional(CONF_NEW_DEVICES_GROUP, default=None): cv.string,
    vol.Optional(CONF_IGNORE_DEVICES): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_DEVICE_DEFAULTS, default=DEVICE_DEFAULTS_SCHEMA({})):
    DEVICE_DEFAULTS_SCHEMA,
    vol.Optional(CONF_DEVICES, default={}): vol.Schema({
        cv.string: {
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_TYPE):
                vol.Any(TYPE_DIMMABLE, TYPE_SWITCHABLE, TYPE_HYBRID),
            vol.Optional(CONF_ALIASSES, default=[]):
                vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_FIRE_EVENT, default=False): cv.boolean,
            vol.Optional(CONF_SIGNAL_REPETITIONS): vol.Coerce(int),
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
        'newkaku': TYPE_HYBRID,
    }
    protocol = device_id.split('_')[0]
    return entity_type_mapping.get(protocol, None)


def entity_class_for_type(entity_type):
    """Translate entity type to entity class.

    Async friendly.
    """
    entity_device_mapping = {
        # sends only 'dim' commands not compatible with on/off switches
        TYPE_DIMMABLE: DimmableRflinkLight,
        # sends only 'on/off' commands not advices with dimmers and signal
        # repetition
        TYPE_SWITCHABLE: RflinkLight,
        # sends 'dim' and 'on' command to support both dimmers and on/off
        # switches. Not compatible with signal repetition.
        TYPE_HYBRID: HybridRflinkLight,
    }

    return entity_device_mapping.get(entity_type, RflinkLight)


def devices_from_config(domain_config, hass=None):
    """Parse configuration and add Rflink light devices."""
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

        is_hybrid = entity_class is HybridRflinkLight

        # Make user aware this can cause problems
        repetitions_enabled = device_config[CONF_SIGNAL_REPETITIONS] != 1
        if is_hybrid and repetitions_enabled:
            _LOGGER.warning(
                "Hybrid type for %s not compatible with signal "
                "repetitions. Please set 'dimmable' or 'switchable' "
                "type explicity in configuration", device_id)

        device = entity_class(device_id, hass, **device_config)
        devices.append(device)

        # Register entity (and aliasses) to listen to incoming rflink events
        for _id in [device_id] + config[CONF_ALIASSES]:
            hass.data[DATA_ENTITY_LOOKUP][
                EVENT_KEY_COMMAND][_id].append(device)

    return devices


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Rflink light platform."""
    async_add_devices(devices_from_config(config, hass))

    # Add new (unconfigured) devices to user desired group
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

        device_config = config[CONF_DEVICE_DEFAULTS]
        device = entity_class(device_id, hass, **device_config)
        async_add_devices([device])

        # Register entity to listen to incoming Rflink events
        hass.data[DATA_ENTITY_LOOKUP][
            EVENT_KEY_COMMAND][device_id].append(device)

        # Make sure the event is processed by the new entity
        device.handle_event(event)

        # Maybe add to new devices group
        if new_devices_group:
            yield from new_devices_group.async_update_tracked_entity_ids(
                list(new_devices_group.tracking) + [device.entity_id])

    hass.data[DATA_DEVICE_REGISTER][EVENT_KEY_COMMAND] = add_new_device


class RflinkLight(SwitchableRflinkDevice, Light):
    """Representation of a Rflink light."""

    @property
    def entity_id(self):
        """Return entity id."""
        return "light.{}".format(self.name)


class DimmableRflinkLight(SwitchableRflinkDevice, Light):
    """Rflink light device that support dimming."""

    _brightness = 255

    @property
    def entity_id(self):
        """Return entity id."""
        return "light.{}".format(self.name)

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the device on."""
        if ATTR_BRIGHTNESS in kwargs:
            # rflink only support 16 brightness levels
            self._brightness = int(kwargs[ATTR_BRIGHTNESS] / 17) * 17

        # turn on light at the requested dim level
        yield from self._async_handle_command('dim', self._brightness)

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS


class HybridRflinkLight(SwitchableRflinkDevice, Light):
    """Rflink light device that sends out both dim and on/off commands.

    Used for protocols which support lights that are not exclusively on/off
    style. For example KlikAanKlikUit supports both on/off and dimmable light
    switches using the same protocol. This type allows unconfigured
    KlikAanKlikUit devices to support dimming without breaking support for
    on/off switches.

    This type is not compatible with signal repetitions as the 'dim' and 'on'
    command are send sequential and multiple 'on' commands to a dimmable
    device can cause the dimmer to switch into a pulsating brightness mode.
    Which results in a nice house disco :)
    """

    _brightness = 255

    @property
    def entity_id(self):
        """Return entity id."""
        return "light.{}".format(self.name)

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the device on and set dim level."""
        if ATTR_BRIGHTNESS in kwargs:
            # rflink only support 16 brightness levels
            self._brightness = int(kwargs[ATTR_BRIGHTNESS] / 17) * 17

        # if receiver supports dimming this will turn on the light
        # at the requested dim level
        yield from self._async_handle_command('dim', self._brightness)

        # if the receiving device does not support dimlevel this
        # will ensure it is turned on when full brightness is set
        if self._brightness == 255:
            yield from self._async_handle_command('turn_on')

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS
