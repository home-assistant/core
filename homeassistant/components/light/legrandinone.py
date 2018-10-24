"""
Support for IOBL lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.iobl/
"""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, PLATFORM_SCHEMA, SUPPORT_BRIGHTNESS, Light)
from homeassistant.components.legrandinone import (
    CONF_AUTOMATIC_ADD, CONF_DEVICE_DEFAULTS,
    CONF_DEVICES, CONF_FIRE_EVENT, DATA_DEVICE_REGISTER,
    DEVICE_DEFAULTS_SCHEMA, CONF_MEDIA, CONF_COMM_MODE,
    EVENT_KEY_COMMAND, EVENT_KEY_ID, SwitchableIoblDevice, cv,
    vol)
from homeassistant.const import (CONF_NAME, CONF_TYPE)

DEPENDENCIES = ['legrandinone']

_LOGGER = logging.getLogger(__name__)

TYPE_DIMMABLE = 'dimmable'
TYPE_SWITCHABLE = 'switchable'
TYPE_TOGGLE = 'toggle'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICE_DEFAULTS, default=DEVICE_DEFAULTS_SCHEMA({})):
        DEVICE_DEFAULTS_SCHEMA,
    vol.Optional(CONF_AUTOMATIC_ADD, default=True): cv.boolean,
    vol.Optional(CONF_DEVICES, default={}): {
        cv.string: vol.Schema({
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_TYPE):
                vol.Any(TYPE_DIMMABLE, TYPE_SWITCHABLE,
                        TYPE_TOGGLE),
            vol.Optional(CONF_FIRE_EVENT): cv.boolean,
            vol.Optional(CONF_MEDIA, default='plc'): cv.string,
            vol.Optional(CONF_COMM_MODE, default='unicast'): cv.string,
        })
    },
}, extra=vol.ALLOW_EXTRA)


def entity_class_for_type(entity_type):
    """Translate entity type to entity class.

    Async friendly.
    """
    entity_device_mapping = {
        # sends 'dim', 'off' and 'on' command to support both dimmers and on/off
        # switches.
        TYPE_DIMMABLE: DimmableIoblLight,
        # sends only 'on/off' commands not advices with dimmers 
        TYPE_SWITCHABLE: IoblLight,
        # sends only 'on' commands for switches which turn on and off
        # using the same 'on' command for both.
        TYPE_TOGGLE: ToggleIoblLight,
    }

    return entity_device_mapping.get(entity_type, IoblLight)


def devices_from_config(domain_config, hass=None):
    """Parse configuration and add IOBL light devices."""
    devices = []
    for device_id, config in domain_config[CONF_DEVICES].items():
        # Determine which kind of entity to create
        if CONF_TYPE in config:
            # Remove type from config to not pass it as and argument to entity
            # instantiation
            entity_type = config.pop(CONF_TYPE)
        else:
            entity_type = TYPE_SWITCHABLE

        entity_class = entity_class_for_type(entity_type)

        device_config = dict(domain_config[CONF_DEVICE_DEFAULTS], **config)

        device = entity_class(device_id, hass, **device_config)
        devices.append(device)

    return devices


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the IOBL light platform."""
    async_add_entities(devices_from_config(config))

    async def add_new_device(event):
        """Check if device is known, otherwise add to list of known devices."""
        device_id = event[EVENT_KEY_ID]

        entity_type = entity_type_for_device_id(event[EVENT_KEY_ID])
        entity_class = entity_class_for_type(entity_type)

        device_config = config[CONF_DEVICE_DEFAULTS]
        device = entity_class(device_id, initial_event=event, **device_config)
        async_add_entities([device])

    if config[CONF_AUTOMATIC_ADD]:
        hass.data[DATA_DEVICE_REGISTER][EVENT_KEY_COMMAND] = add_new_device


class IoblLight(SwitchableIoblDevice, Light):

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self._async_handle_command('turn_on')

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self._async_handle_command('turn_off')


class DimmableIoblLight(SwitchableIoblDevice, Light):
    """IOBL light device that support dimming."""

    def __init__(self, *args, **kwargs):
        """Initialize device type and unit number."""
        self.iobl_type = 'light'
        self.iobl_unit = '0'
        super().__init__(*args, **kwargs)

    _brightness = 255

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = int(kwargs[ATTR_BRIGHTNESS])
            # Turn on light at the requested dim level
            await self._async_handle_command('dim', self._brightness)
        else:
            await self._async_handle_command('turn_on')


    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS


class ToggleIoblLight(SwitchableIoblDevice, Light):
    """Iobl light device which sends out only 'on' commands."""

    def __init__(self, *args, **kwargs):
        """Initialize device type and unit number."""
        self.iobl_type = 'light'
        self.iobl_unit = '0'
        super().__init__(*args, **kwargs)

    @property
    def entity_id(self):
        """Return entity id."""
        return "light.{}".format(self.name)

    def _handle_event(self, event):
        """Adjust state if IOBL picks up a remote command for this device."""
        command = event['command']
        if command == 'on':
            # if the state is unknown or false, it gets set as true
            # if the state is true, it gets set as false
            self._state = self._state in [None, False]

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self._async_handle_command('toggle')

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self._async_handle_command('toggle')
