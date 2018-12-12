"""
Support for legrandinone Cover devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.legrandinone/
"""
import logging

import voluptuous as vol

from homeassistant.components.legrandinone import (
    DATA_ENTITY_LOOKUP, CONF_MEDIA, CONF_COMM_MODE,
    DEVICE_DEFAULTS_SCHEMA, EVENT_KEY_COMMAND, IOBL_PROTOCOL_HANDLE,
    DEVICE_TYPE_AUTOMATION, DATA_DEVICE_REGISTER,
    EVENT_KEY_ID, LegrandInOneCommand)
from homeassistant.components.cover import (
    CoverDevice, PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_NAME


DEPENDENCIES = ['legrandinone']

_LOGGER = logging.getLogger(__name__)


CONF_DEVICE_DEFAULTS = 'device_defaults'
CONF_DEVICES = 'devices'
CONF_AUTOMATIC_ADD = 'automatic_add'
CONF_RECONNECT_INTERVAL = 'reconnect_interval'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICE_DEFAULTS, default=DEVICE_DEFAULTS_SCHEMA({})):
    DEVICE_DEFAULTS_SCHEMA,
    vol.Optional(CONF_AUTOMATIC_ADD, default=True): cv.boolean,
    vol.Optional(CONF_DEVICES, default={}): vol.Schema({
        cv.string: {
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_MEDIA, default='plc'): cv.string,
            vol.Optional(CONF_COMM_MODE, default='unicast'): cv.string,
        },
    }),
})


def devices_from_config(domain_config, hass):
    """Parse configuration and add IOBL cover devices."""
    devices = []
    for device_id, config in domain_config[CONF_DEVICES].items():
        device_config = dict(domain_config[CONF_DEVICE_DEFAULTS], **config)
        device = LegrandInOneCover(device_id,
                                   hass.data[IOBL_PROTOCOL_HANDLE],
                                   **device_config)
        devices.append(device)

    return devices


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the IOBL cover platform."""
    async_add_entities(devices_from_config(config, hass))

    async def add_new_device(event):
        """Check if device is known, otherwise add to list of known devices."""
        device_id = event[EVENT_KEY_ID]

        device_config = config[CONF_DEVICE_DEFAULTS]
        device = LegrandInOneCover(device_id, hass.data[IOBL_PROTOCOL_HANDLE],
                                   initial_event=event, **device_config)
        async_add_entities([device])
        hass.data[DATA_ENTITY_LOOKUP][
            EVENT_KEY_COMMAND][device_id].append(device)

    if config[CONF_AUTOMATIC_ADD]:
        hass.data[DATA_DEVICE_REGISTER][EVENT_KEY_COMMAND][
            DEVICE_TYPE_AUTOMATION] = add_new_device


class LegrandInOneCover(LegrandInOneCommand, CoverDevice):
    """IOBL entity which can switch on/stop/off (eg: cover)."""

    def __init__(self, *args, **kwargs):
        """Initialize device type and unit number."""
        self.iobl_type = 'automation'
        self.iobl_unit = '2'
        super().__init__(*args, **kwargs)

    def _handle_event(self, event):

        command = event['what']
        if command in ['move_up']:
            self._state = True
        elif command in ['move_down']:
            self._state = False

    @property
    def should_poll(self):
        """No polling available in iobl cover."""
        return False

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return not self._state

    @property
    def assumed_state(self):
        """Return True because covers can be stopped midway."""
        return True

    def async_close_cover(self, **kwargs):
        """Turn the device close."""
        return self._async_handle_command("close_cover")

    def async_open_cover(self, **kwargs):
        """Turn the device open."""
        return self._async_handle_command("open_cover")

    def async_stop_cover(self, **kwargs):
        """Turn the device stop."""
        return self._async_handle_command("stop_cover")
