"""
Support for ZoneMinder switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.zoneminder/
"""
import logging

import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.components.zoneminder import DOMAIN as ZONEMINDER_DOMAIN
from homeassistant.const import (CONF_COMMAND_ON, CONF_COMMAND_OFF)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zoneminder']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COMMAND_ON): cv.string,
    vol.Required(CONF_COMMAND_OFF): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the ZoneMinder switch platform."""
    from zoneminder.monitor import MonitorState
    on_state = MonitorState(config.get(CONF_COMMAND_ON))
    off_state = MonitorState(config.get(CONF_COMMAND_OFF))

    zm_client = hass.data[ZONEMINDER_DOMAIN]

    monitors = zm_client.get_monitors()
    if not monitors:
        _LOGGER.warning('Could not fetch monitors from ZoneMinder')
        return

    switches = []
    for monitor in monitors:
        switches.append(ZMSwitchMonitors(monitor, on_state, off_state))
    add_entities(switches)


class ZMSwitchMonitors(SwitchDevice):
    """Representation of a ZoneMinder switch."""

    icon = 'mdi:record-rec'

    def __init__(self, monitor, on_state, off_state):
        """Initialize the switch."""
        self._monitor = monitor
        self._on_state = on_state
        self._off_state = off_state
        self._state = None

    @property
    def name(self):
        """Return the name of the switch."""
        return '{} State'.format(self._monitor.name)

    def update(self):
        """Update the switch value."""
        self._state = self._monitor.function == self._on_state

    @property
    def is_on(self):
        """Return True if entity is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the entity on."""
        self._monitor.function = self._on_state

    def turn_off(self, **kwargs):
        """Turn the entity off."""
        self._monitor.function = self._off_state
