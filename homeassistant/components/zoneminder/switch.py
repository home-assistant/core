"""Support for ZoneMinder switches."""
import logging
from typing import Callable, List, Optional

import voluptuous as vol
from zoneminder.monitor import Monitor, MonitorState

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COMMAND_OFF, CONF_COMMAND_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .common import get_client_from_data, get_platform_configs

_LOGGER = logging.getLogger(__name__)

MONITOR_STATES = {
    MonitorState[name].value: MonitorState[name]
    for name in dir(MonitorState)
    if not name.startswith("_")
}
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_COMMAND_ON): vol.All(vol.In(MONITOR_STATES.keys())),
        vol.Required(CONF_COMMAND_OFF): vol.All(vol.In(MONITOR_STATES.keys())),
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], Optional[bool]], None],
) -> None:
    """Set up the sensor config entry."""
    zm_client = get_client_from_data(hass, config_entry.unique_id)
    monitors = await hass.async_add_job(zm_client.get_monitors)

    if not monitors:
        _LOGGER.warning("Could not fetch monitors from ZoneMinder")
        return

    switches = []
    for monitor in monitors:
        for config in get_platform_configs(hass, SWITCH_DOMAIN):
            on_state = MONITOR_STATES[config[CONF_COMMAND_ON]]
            off_state = MONITOR_STATES[config[CONF_COMMAND_OFF]]

            switches.append(
                ZMSwitchMonitors(monitor, on_state, off_state, config_entry)
            )

    async_add_entities(switches, True)


class ZMSwitchMonitors(SwitchEntity):
    """Representation of a ZoneMinder switch."""

    icon = "mdi:record-rec"

    def __init__(
        self,
        monitor: Monitor,
        on_state: MonitorState,
        off_state: MonitorState,
        config_entry: ConfigEntry,
    ):
        """Initialize the switch."""
        self._monitor = monitor
        self._on_state = on_state
        self._off_state = off_state
        self._config_entry = config_entry
        self._state = None

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return f"{self._config_entry.unique_id}_{self._monitor.id}_switch_{self._on_state.value}_{self._off_state.value}"

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
