"""
Support for Velbus lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/velbus/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.const import CONF_NAME, CONF_DEVICES
from homeassistant.components.light import Light, PLATFORM_SCHEMA
from homeassistant.core import callback
from homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['python-velbus==2.0.8']
DEPENDENCIES = ['velbus']
DOMAIN = 'light'

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICES): vol.All(cv.ensure_list, [
        {
            vol.Required('module'): cv.positive_int,
            vol.Required('channel'): cv.positive_int,
            vol.Required(CONF_NAME): cv.string,
            vol.Optional('is_pushbutton'): cv.boolean
        }
    ])
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Lights."""
    add_devices(VelbusLight(light) for light in config[CONF_DEVICES])
    return True


class VelbusLight(Light):
    """Representation of a Velbus Light."""

    def __init__(self, light):
        """Initialize a Velbus light."""
        self._name = light[CONF_NAME]
        self._module = light['module']
        self._channel = light['channel']
        self._state = False

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Add listener for Velbus messages on bus."""
        self.hass.data['VelbusController'].subscribe(self._on_message)
        self.get_status()

    @callback
    def _on_message(self, message):
        import velbus
        if isinstance(message, velbus.RelayStatusMessage) and \
           message.address == self._module and \
           message.channel == self._channel:
            self._state = message.is_on()
            self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def is_on(self):
        """Return true if the light is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        import velbus
        message = velbus.SwitchRelayOnMessage()
        message.set_defaults(self._module)
        message.relay_channels = [self._channel]
        self.hass.data['VelbusController'].send(message)

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        import velbus
        message = velbus.SwitchRelayOffMessage()
        message.set_defaults(self._module)
        message.relay_channels = [self._channel]
        self.hass.data['VelbusController'].send(message)

    def get_status(self):
        """Retrieve current status."""
        import velbus
        message = velbus.ModuleStatusRequestMessage()
        message.set_defaults(self._module)
        message.channels = [self._channel]
        self.hass.data['VelbusController'].send(message)
