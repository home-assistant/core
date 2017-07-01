"""
Support for Velbus switches.

For more details about this platform, please refer to the documentation at XXX
"""

import asyncio
import logging
import time

import voluptuous as vol

from homeassistant.const import CONF_NAME, CONF_DEVICES, CONF_TYPE
from homeassistant.components.switch import SwitchDevice, PLATFORM_SCHEMA
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

SINGLE_SWITCH_SCHEMA = {
    vol.Required('module'): cv.positive_int,
    vol.Required('channel'): cv.positive_int,
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_TYPE): cv.string
}

DOUBLE_SWITCH_SCHEMA = {
    vol.Required('module'): cv.positive_int,
    vol.Required('open_channel'): cv.positive_int,
    vol.Required('close_channel'): cv.positive_int,
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_TYPE): cv.string
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICES):
        vol.All(cv.ensure_list,
                [vol.Any(SINGLE_SWITCH_SCHEMA, DOUBLE_SWITCH_SCHEMA)])
})

REQUIREMENTS = ['python-velbus==2.0.10']
DEPENDENCIES = ['velbus']
DOMAIN = 'switch'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Switch."""
    devices = []
    for switch in config[CONF_DEVICES]:
        if switch[CONF_TYPE] == 'single':
            devices.push(VelbusSingleSwitch(switch))
        elif switch[CONF_TYPE] == 'double':
            devices.push(VelbusDoubleSwitch(switch))
    add_devices(devices)
    return True


class VelbusSingleSwitch(SwitchDevice):
    """Representation of a single switch."""

    def __init__(self, switch):
        """Initialize a Velbus switch."""
        self._name = switch[CONF_NAME]
        self._module = switch['module']
        self._channel = switch['channel']
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
        self.hass.data['VelbusController'].send(message)

    def turn_off(self, **kwargs):
        """Instruct the switch to turn off."""
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


class VelbusDoubleSwitch(SwitchDevice):
    """Representation of a double switch."""

    def __init__(self, switch):
        """Initialize the curtain."""
        self._close_channel_state = None
        self._open_channel_state = None
        self._name = switch[CONF_NAME]
        self._module = switch['module']
        self._open_channel = switch['open_channel']
        self._closed_channel = switch['close_channel']

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Add listener for Velbus messages on bus."""
        self.hass.data['VelbusController'].subscribe(self._on_message)
        self.get_status()

    @callback
    def _on_message(self, message):
        import velbus
        if isinstance(message, velbus.RelayStatusMessage):
            if message.address == self._module:
                if message.channel == self._close_channel:
                    self._close_channel_state = message.is_on()
                    self.schedule_update_ha_state()
                if message.channel == self._open_channel:
                    self._open_channel_State = message.is_on()
                    self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def is_on(self):
        """Return true if switch is closed."""
        return self._close_channel_state

    def turn_on(self, **kwargs):
        """Instruct the switch to close."""
        self._relay_off(self._open_channel)
        time.sleep(0.3)
        self._relay_on(self._close_channel)

    def _relay_on(self, channel):
        import velbus
        message = velbus.SwitchRelayOnMessage()
        message.set_defaults(self._module)
        message.relay_channels = [channel]
        self.hass.data['VelbusController'].send(message)

    def _relay_off(self, channel):
        import velbus
        message = velbus.SwitchRelayOffMessage()
        message.set_defaults(self._module)
        message.relay_channels = [channel]
        self.hass.data['VelbusController'].send(message)

    def turn_off(self, **kwargs):
        """Instruct the switch to open."""
        self._relay_off(self._close_channel)
        time.sleep(0.3)
        self._relay_on(self._open_channel)

    def get_status(self):
        """Retrieve current status."""
        import velbus
        message = velbus.ModuleStatusRequestMessage()
        message.set_defaults(self._module)
        message.channels = [self._open_channel, self._close_channel]
        self.hass.data['VelbusController'].send(message)
