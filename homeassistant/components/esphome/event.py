"""Support for ESPHome event components."""

from __future__ import annotations

from functools import partial

from aioesphomeapi import EntityInfo, Event, EventInfo

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import callback
from homeassistant.util.enum import try_parse_enum

from .entity import EsphomeEntity, platform_async_setup_entry


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

    @callback
    def _on_device_update(self) -> None:
        """Call when device updates or entry data changes."""
        super()._on_device_update()
        if self._entry_data.available:
            # Event entities should go available directly
            # when the device comes online and not wait
            # for the next data push.
            self.async_write_ha_state()


async_setup_entry = partial(
    platform_async_setup_entry,
    info_type=EventInfo,
    entity_type=EsphomeEvent,
    state_type=Event,
)
