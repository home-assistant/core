"""
Support for Velbus lights.

For more details about this platform, please refer to the documentation at XXX
"""
from homeassistant.components.light import Light
import asyncio
import logging
import velbus
from homeassistant.components.velbus import (VELBUS_MESSAGE)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities,  # noqa: D401
                         discovery_info=None):
    """Setup Lights."""
    controller = hass.data['VelbusController']
    lights = []
    for light in discovery_info:
        lights.append(VelbusLight(hass, light, controller))
    async_add_entities(lights)
    delay = 10
    loop = asyncio.get_event_loop()
    for light in lights:
        loop.call_later(delay, light.get_status)
        delay = delay + 2
    return True


class VelbusLight(Light):
    """Representation of a Velbus Light."""

    def __init__(self, hass, light, controller):
        """Initialize a Velbus light."""
        self._name = light['name']
        self._module = light['module']
        self._channel = light['channel']
        self._state = False
        self._hass = hass
        self._controller = controller

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Add listener for Velbus messages on bus."""
        async_dispatcher_connect(
            self._hass, VELBUS_MESSAGE, self._on_message
        )

    @callback
    def _on_message(self, message):
        if isinstance(message, velbus.RelayStatusMessage) and \
           message.address == self._module and \
           message.channel == self._channel:
            self._state = message.is_on()
            self._hass.async_add_job(self.async_update_ha_state())

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
        message = velbus.SwitchRelayOnMessage()
        message.set_defaults(self._module)
        message.relay_channels = [self._channel]
        self._controller.send(message)

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        message = velbus.SwitchRelayOffMessage()
        message.set_defaults(self._module)
        message.relay_channels = [self._channel]
        self._controller.send(message)

    def get_status(self):
        """Retrieve current status."""
        message = velbus.ModuleStatusRequestMessage()
        message.set_defaults(self._module)
        message.channels = [self._channel]
        self._controller.send(message)
