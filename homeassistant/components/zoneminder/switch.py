"""Support for ZoneMinder switches."""
import logging

import voluptuous as vol
from zoneminder.monitor import MonitorState

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import CONF_COMMAND_OFF, CONF_COMMAND_ON
import homeassistant.helpers.config_validation as cv

from . import DOMAIN as ZONEMINDER_DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_COMMAND_ON): cv.string,
        vol.Required(CONF_COMMAND_OFF): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the ZoneMinder switch platform."""

    on_state = MonitorState(config.get(CONF_COMMAND_ON))
    off_state = MonitorState(config.get(CONF_COMMAND_OFF))

    switches = []
    for zm_client in hass.data[ZONEMINDER_DOMAIN].values():
        monitors = zm_client.get_monitors()
        if not monitors:
            _LOGGER.warning("Could not fetch monitors from ZoneMinder")
            return

        for monitor in monitors:
            switches.append(ZMSwitchMonitors(monitor, on_state, off_state))
    add_entities(switches)


class ZMSwitchMonitors(SwitchEntity):
    """Representation of a ZoneMinder switch."""

    icon = "mdi:record-rec"

    def __init__(self, monitor, on_state, off_state):
        """Initialize the switch."""
        self._monitor = monitor
        self._on_state = on_state
        self._off_state = off_state
        self._state = None

    @property
    def name(self):
        """Return the name of the switch."""
        return f"{self._monitor.name} State"

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
