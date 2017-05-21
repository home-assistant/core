"""
Support for Velbus switches.

For more details about this platform, please refer to the documentation at XXX
"""
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.components.binary_sensor import BinarySensorDevice

import asyncio
import logging
import velbus

from homeassistant.components.velbus import (VELBUS_MESSAGE)

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities,  # noqa: D401
                         discovery_info=None):
    """Setup Velbus switches."""
    controller = hass.data['VelbusController']
    async_add_entities(
        VelbusSwitch(hass, switch, controller) for switch in discovery_info)
    return True


class VelbusSwitch(BinarySensorDevice):
    """Representation of a Velbus Switch."""

    def __init__(self, hass, switch, controller):
        """Initialize a Velbus light."""
        self._name = switch['name']
        self._module = switch['module']
        self._channel = switch['channel']
        self._is_pushbutton = 'is_pushbutton' in switch \
                              and switch['is_pushbutton']
        self._state = False
        self._controller = controller
        self._hass = hass

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Add listener for Velbus messages on bus."""
        async_dispatcher_connect(
            self._hass, VELBUS_MESSAGE, self._on_message
        )

    @callback
    def _on_message(self, message):
        if isinstance(message, velbus.PushButtonStatusMessage):
            if message.address == self._module and \
               self._channel in message.get_channels():
                if self._is_pushbutton:
                    if self._channel in message.closed:
                        self._toggle()
                    else:
                        pass
                else:
                    self._toggle()

    def _toggle(self):
        if self._state is True:
            self._state = False
        else:
            self._state = True
        self._hass.async_add_job(self.async_update_ha_state())

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self._state
