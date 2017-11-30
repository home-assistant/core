"""
Support for Rflink lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.rflink/
"""
import asyncio
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light)
from homeassistant.components.rflink import (
    CONF_ALIASES, CONF_ALIASSES, CONF_AUTOMATIC_ADD, CONF_DEVICE_DEFAULTS,
    CONF_DEVICES, CONF_FIRE_EVENT, CONF_GROUP, CONF_GROUP_ALIASES,
    CONF_GROUP_ALIASSES, CONF_IGNORE_DEVICES, CONF_NOGROUP_ALIASES,
    CONF_NOGROUP_ALIASSES, CONF_SIGNAL_REPETITIONS, DATA_DEVICE_REGISTER,
    DATA_ENTITY_GROUP_LOOKUP, DATA_ENTITY_LOOKUP, DEVICE_DEFAULTS_SCHEMA,
    DOMAIN, EVENT_KEY_COMMAND, EVENT_KEY_ID, SwitchableRflinkDevice, cv,
    remove_deprecated, vol)
from homeassistant.const import (
    CONF_NAME, CONF_PLATFORM, CONF_TYPE, STATE_UNKNOWN)
from homeassistant.helpers.deprecation import get_deprecated

DEPENDENCIES = ['rflink']

_LOGGER = logging.getLogger(__name__)

TYPE_DIMMABLE = 'dimmable'
TYPE_SWITCHABLE = 'switchable'
TYPE_HYBRID = 'hybrid'
TYPE_TOGGLE = 'toggle'

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
                vol.Any(TYPE_DIMMABLE, TYPE_SWITCHABLE,
                        TYPE_HYBRID, TYPE_TOGGLE),
            vol.Optional(CONF_ALIASES, default=[]):
                vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_GROUP_ALIASES, default=[]):
                vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_NOGROUP_ALIASES, default=[]):
                vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_FIRE_EVENT): cv.boolean,
            vol.Optional(CONF_SIGNAL_REPETITIONS): vol.Coerce(int),
            vol.Optional(CONF_GROUP, default=True): cv.boolean,
            # deprecated config options
            vol.Optional(CONF_ALIASSES):
                vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_GROUP_ALIASSES):
                vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_NOGROUP_ALIASSES):
                vol.All(cv.ensure_list, [cv.string]),
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
        # sends only 'on' commands for switches which turn on and off
        # using the same 'on' command for both.
        TYPE_TOGGLE: ToggleRflinkLight,
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
        remove_deprecated(device_config)

        is_hybrid = entity_class is HybridRflinkLight

        # Make user aware this can cause problems
        repetitions_enabled = device_config[CONF_SIGNAL_REPETITIONS] != 1
        if is_hybrid and repetitions_enabled:
            _LOGGER.warning(
                "Hybrid type for %s not compatible with signal "
                "repetitions. Please set 'dimmable' or 'switchable' "
                "type explicitly in configuration", device_id)

        device = entity_class(device_id, hass, **device_config)
        devices.append(device)

        # Register entity (and aliases) to listen to incoming rflink events

        # Device id and normal aliases respond to normal and group command
        hass.data[DATA_ENTITY_LOOKUP][
            EVENT_KEY_COMMAND][device_id].append(device)
        if config[CONF_GROUP]:
            hass.data[DATA_ENTITY_GROUP_LOOKUP][
                EVENT_KEY_COMMAND][device_id].append(device)
        for _id in get_deprecated(config, CONF_ALIASES, CONF_ALIASSES):
            hass.data[DATA_ENTITY_LOOKUP][
                EVENT_KEY_COMMAND][_id].append(device)
            hass.data[DATA_ENTITY_GROUP_LOOKUP][
                EVENT_KEY_COMMAND][_id].append(device)
        # group_aliases only respond to group commands
        for _id in get_deprecated(
                config, CONF_GROUP_ALIASES, CONF_GROUP_ALIASSES):
            hass.data[DATA_ENTITY_GROUP_LOOKUP][
                EVENT_KEY_COMMAND][_id].append(device)
        # nogroup_aliases only respond to normal commands
        for _id in get_deprecated(
                config, CONF_NOGROUP_ALIASES, CONF_NOGROUP_ALIASSES):
            hass.data[DATA_ENTITY_LOOKUP][
                EVENT_KEY_COMMAND][_id].append(device)

    return devices


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Rflink light platform."""
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

        # Turn on light at the requested dim level
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


class ToggleRflinkLight(SwitchableRflinkDevice, Light):
    """Rflink light device which sends out only 'on' commands.

    Some switches like for example Livolo light switches use the
    same 'on' command to switch on and switch off the lights.
    If the light is on and 'on' gets sent, the light will turn off
    and if the light is off and 'on' gets sent, the light will turn on.
    """

    @property
    def entity_id(self):
        """Return entity id."""
        return "light.{}".format(self.name)

    def _handle_event(self, event):
        """Adjust state if Rflink picks up a remote command for this device."""
        self.cancel_queued_send_commands()

        command = event['command']
        if command == 'on':
            # if the state is unknown or false, it gets set as true
            # if the state is true, it gets set as false
            self._state = self._state in [STATE_UNKNOWN, False]

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the device on."""
        yield from self._async_handle_command('toggle')

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the device off."""
        yield from self._async_handle_command('toggle')
