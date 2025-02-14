"""Support for Bosch Alarm Panel outputs as switches."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

_LOGGER = logging.getLogger(__name__)


class PanelOutputEntity(SwitchEntity):
    """An output entity for a bosch alarm panel."""

    def __init__(self, id, output, panel_conn) -> None:
        """Set up an output entity for a bosch alarm panel."""
        self._id = id
        self._output = output
        self._panel = panel_conn.panel
        self._observer = output.status_observer
        self._attr_has_entity_name = True
        self._attr_device_info = panel_conn.device_info()
        self._attr_unique_id = f"{panel_conn.unique_id}_output_{self._id}"
        self._attr_should_poll = False

    async def async_added_to_hass(self) -> None:
        """Observe state changes."""
        self._observer.attach(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing state changes."""
        self._observer.detach(self.schedule_update_ha_state)

    @property
    def is_on(self) -> bool:
        """Check if this entity is on."""
        return self._output.is_active()

    @property
    def name(self) -> str:
        """The name for this output entity."""
        return self._output.name

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on this output."""
        await self._panel.set_output_active(self._id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off this output."""
        await self._panel.set_output_inactive(self._id)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch entities for outputs."""

    panel_conn = config_entry.runtime_data
    panel = panel_conn.panel

    async_add_entities(
        PanelOutputEntity(output_id, output, panel_conn)
        for (output_id, output) in panel.outputs.items()
    )
