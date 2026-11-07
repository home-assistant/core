"""Support for ZoneMinder switches."""

from typing import Any, override

from zoneminder.monitor import Monitor, MonitorState

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_COMMAND_OFF, CONF_COMMAND_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ZoneMinderConfigEntry
from .const import MONITOR_FUNCTIONS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZoneMinderConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ZoneMinder switch platform."""
    on_state = MONITOR_FUNCTIONS[entry.options[CONF_COMMAND_ON]]
    off_state = MONITOR_FUNCTIONS[entry.options[CONF_COMMAND_OFF]]
    async_add_entities(
        ZMSwitchMonitors(monitor, entry.entry_id, on_state, off_state)
        for monitor in entry.runtime_data.monitors
    )


class ZMSwitchMonitors(SwitchEntity):
    """Representation of a ZoneMinder switch."""

    icon = "mdi:record-rec"

    def __init__(
        self,
        monitor: Monitor,
        entry_id: str,
        on_state: MonitorState,
        off_state: MonitorState,
    ) -> None:
        """Initialize the switch."""
        self._monitor = monitor
        self._on_state = on_state
        self._off_state = off_state
        self._state: bool | None = None
        self._attr_name = f"{monitor.name} State"
        self._attr_unique_id = f"{entry_id}_{monitor.id}_state"

    def update(self) -> None:
        """Update the switch value."""
        self._monitor.update_monitor()
        function = self._monitor.function
        self._state = None if function is None else function == self._on_state

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        return self._state

    @override
    def turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._monitor.function = self._on_state

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._monitor.function = self._off_state
