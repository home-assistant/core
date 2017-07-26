"""
Support for Velbus switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.velbus/
"""

import asyncio
import logging

import voluptuous as vol

from homeassistant.const import CONF_NAME, CONF_DEVICES
from homeassistant.components.switch import SwitchDevice, PLATFORM_SCHEMA
from homeassistant.components.velbus import DOMAIN
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

SWITCH_SCHEMA = {
    vol.Required('module'): cv.positive_int,
    vol.Required('channel'): cv.positive_int,
    vol.Required(CONF_NAME): cv.string
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICES):
        vol.All(cv.ensure_list, [SWITCH_SCHEMA])
})

DEPENDENCIES = ['velbus']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Switch."""
    velbus = hass.data[DOMAIN]
    devices = []

    for switch in config[CONF_DEVICES]:
        devices.append(VelbusSwitch(switch, velbus))
    add_devices(devices)
    return True


class VelbusSwitch(SwitchDevice):
    """Representation of a switch."""

    def __init__(self, switch, velbus):
        """Initialize a Velbus switch."""
        self._velbus = velbus
        self._name = switch[CONF_NAME]
        self._module = switch['module']
        self._channel = switch['channel']
        self._state = False

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Add listener for Velbus messages on bus."""
        def _init_velbus():
            """Initialize Velbus on startup."""
            self._velbus.subscribe(self._on_message)
            self.get_status()

        yield from self.hass.async_add_job(_init_velbus)

    def _on_message(self, message):
        import velbus
        if isinstance(message, velbus.RelayStatusMessage) and \
           message.address == self._module and \
           message.channel == self._channel:
            self._state = message.is_on()
            self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._name

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Instruct the switch to turn on."""
        import velbus
        message = velbus.SwitchRelayOnMessage()
        message.set_defaults(self._module)
        message.relay_channels = [self._channel]
        self._velbus.send(message)

    def turn_off(self, **kwargs):
        """Instruct the switch to turn off."""
        import velbus
        message = velbus.SwitchRelayOffMessage()
        message.set_defaults(self._module)
        message.relay_channels = [self._channel]
        self._velbus.send(message)

    def get_status(self):
        """Retrieve current status."""
        import velbus
        message = velbus.ModuleStatusRequestMessage()
        message.set_defaults(self._module)
        message.channels = [self._channel]
        self._velbus.send(message)
