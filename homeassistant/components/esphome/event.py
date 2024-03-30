"""Support for ESPHome event components."""

from __future__ import annotations

from aioesphomeapi import EntityInfo, Event, EventInfo
import voluptuous as vol

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import EsphomeEntity, platform_async_setup_entry

CONF_EVENT_TYPES = "event_types"

DEFAULT_NAME = "ESPHome Event"
DEVICE_CLASS_SCHEMA = vol.All(vol.Lower, vol.Coerce(EventDeviceClass))


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
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
        if event_types := static_info.event_types:
            self._attr_event_types = event_types

    @callback
    def _on_state_update(self) -> None:
        super()._on_state_update()
        self._trigger_event(self._state.event_type)
        self.async_write_ha_state()
