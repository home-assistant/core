"""Support for ESPHome event components."""

from __future__ import annotations

from aioesphomeapi import EntityInfo, Event, EventInfo

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.enum import try_parse_enum

from .entity import EsphomeEntity, platform_async_setup_entry
from .entry_data import ESPHomeConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ESPHomeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ESPHome event based on a config entry."""
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        info_type=EventInfo,
        entity_type=EsphomeEvent,
        state_type=Event,
    )


class EsphomeEvent(EsphomeEntity[EventInfo, Event], EventEntity):
    """An event implementation for ESPHome."""

    @callback
    def _on_static_info_update(self, static_info: EntityInfo) -> None:
        """Set attrs from static info."""
        super()._on_static_info_update(static_info)
        static_info = self._static_info
        if event_types := static_info.event_types:
            self._attr_event_types = event_types
        self._attr_device_class = try_parse_enum(
            EventDeviceClass, static_info.device_class
        )

    @callback
    def _on_state_update(self) -> None:
        self._update_state_from_entry_data()
        self._trigger_event(self._state.event_type)
        self.async_write_ha_state()
