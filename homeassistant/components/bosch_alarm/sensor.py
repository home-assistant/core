"""Support for Bosch Alarm Panel History as a sensor."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import HISTORY_ATTR

_LOGGER = logging.getLogger(__name__)


class PanelSensor(SensorEntity):
    """A sensor entity for a bosch alarm panel."""

    def __init__(self, panel_conn, observer) -> None:
        """Set up a sensor entity for a bosch alarm panel."""
        self._panel = panel_conn.panel
        self._attr_has_entity_name = True
        self._attr_device_info = panel_conn.device_info()
        self._attr_should_poll = False
        self._observer = observer

    async def async_added_to_hass(self) -> None:
        """Observe state changes."""
        self._observer.attach(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing state changes."""
        self._observer.detach(self.schedule_update_ha_state)


class PanelHistorySensor(PanelSensor):
    """A history sensor entity for a bosch alarm panel."""

    def __init__(self, panel_conn) -> None:
        """Set up a history sensor entity for a bosch alarm panel."""
        super().__init__(panel_conn, panel_conn.panel.history_observer)
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_unique_id = f"{panel_conn.unique_id}_history"

    @property
    def icon(self) -> str | None:
        """The icon for this history entity."""
        return "mdi:history"

    @property
    def native_value(self) -> str:
        """The state for this history entity."""
        events = self._panel.events
        if events:
            return str(events[-1])
        return "No events"

    @property
    def name(self) -> str:
        """The name for this history entity."""
        return "History"

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """The extra state attributes for this history entity."""
        events = self._panel.events
        return {HISTORY_ATTR + f"_{e.date}": e.message for e in events}


class PanelFaultsSensor(PanelSensor):
    """A faults sensor entity for a bosch alarm panel."""

    def __init__(self, panel_conn) -> None:
        """Set up a faults sensor entity for a bosch alarm panel."""
        super().__init__(panel_conn, panel_conn.panel.faults_observer)
        self._attr_unique_id = f"{panel_conn.unique_id}_faults"

    @property
    def icon(self) -> str:
        """The icon for this faults entity."""
        return "mdi:alert-circle"

    @property
    def native_value(self) -> str:
        """The state of this faults entity."""
        faults = self._panel.panel_faults
        return "\n".join(faults) if faults else "No faults"

    @property
    def name(self) -> str:
        """The name for this faults entity."""
        return "Faults"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a sensor for tracking panel history."""

    panel_conn = config_entry.runtime_data
    async_add_entities([PanelHistorySensor(panel_conn), PanelFaultsSensor(panel_conn)])
