"""Support for ESPHome event components."""

from functools import partial
from typing import TYPE_CHECKING, override

from aioesphomeapi import (
    EntityInfo,
    Event,
    EventInfo,
    InfraredCapability,
    InfraredInfo,
    build_device_unique_id,
)

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.components.infrared import InfraredCommandEventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.enum import try_parse_enum

from .entity import EsphomeEntity, async_entity_device_info, platform_async_setup_entry
from .entry_data import ESPHomeConfigEntry, RuntimeEntryData

PARALLEL_UPDATES = 0


class EsphomeEvent(EsphomeEntity[EventInfo, Event], EventEntity):
    """An event implementation for ESPHome."""

    @callback
    @override
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
    @override
    def _on_state_update(self) -> None:
        self._update_state_from_entry_data()
        self._trigger_event(self._state.event_type)
        self.async_write_ha_state()

    @callback
    @override
    def _on_device_update(self) -> None:
        """Call when device updates or entry data changes."""
        super()._on_device_update()
        if self._entry_data.available:
            # Event entities should go available directly
            # when the device comes online and not wait
            # for the next data push.
            self.async_write_ha_state()


@callback
def _async_add_infrared_command_events(
    entry_data: RuntimeEntryData,
    async_add_entities: AddConfigEntryEntitiesCallback,
    added_unique_ids: set[str],
    infos: list[EntityInfo],
) -> None:
    """Add the companion event entity of every infrared receiver."""
    device_info = entry_data.device_info
    if TYPE_CHECKING:
        assert device_info is not None
    entities: list[InfraredCommandEventEntity] = []
    for info in infos:
        if TYPE_CHECKING:
            assert isinstance(info, InfraredInfo)
        if not info.capabilities & InfraredCapability.RECEIVER:
            continue
        unique_id = build_device_unique_id(device_info.mac_address, info)
        if unique_id in added_unique_ids:
            continue
        added_unique_ids.add(unique_id)
        entities.append(
            InfraredCommandEventEntity(
                unique_id, async_entity_device_info(device_info, info)
            )
        )
    if entities:
        async_add_entities(entities)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ESPHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ESPHome event platform."""
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        info_type=EventInfo,
        entity_type=EsphomeEvent,
        state_type=Event,
    )

    entry_data = entry.runtime_data
    entry_data.cleanup_callbacks.append(
        entry_data.async_register_static_info_callback(
            InfraredInfo,
            partial(
                _async_add_infrared_command_events,
                entry_data,
                async_add_entities,
                set(),
            ),
        )
    )
