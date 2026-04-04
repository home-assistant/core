"""Event platform for OpenDisplay devices — button press/release events."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OpenDisplayConfigEntry
from .entity import OpenDisplayEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class OpenDisplayEventEntityDescription(EventEntityDescription):
    """Describes an OpenDisplay button event entity."""

    byte_index: int
    button_id: int


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenDisplayConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OpenDisplay event entities from binary_inputs device config."""
    coordinator = entry.runtime_data.coordinator

    descriptions = [
        OpenDisplayEventEntityDescription(
            key=f"button_{bi.instance_number}_{button_id}",
            translation_key="button",
            translation_placeholders={"number": str(button_id + 1)},
            device_class=EventDeviceClass.BUTTON,
            event_types=["button_down", "button_up"],
            byte_index=bi.button_data_byte_index,
            button_id=button_id,
        )
        for bi in entry.runtime_data.device_config.binary_inputs
        for button_id in range(8)
        if bi.input_flags & (1 << button_id)  # input_flags is an isused bitmask
    ]

    active_unique_ids = {f"{coordinator.address}-{d.key}" for d in descriptions}
    entity_registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        if (
            entity_entry.domain == "event"
            and entity_entry.unique_id not in active_unique_ids
        ):
            entity_registry.async_remove(entity_entry.entity_id)

    async_add_entities(
        OpenDisplayEventEntity(coordinator, description) for description in descriptions
    )


class OpenDisplayEventEntity(OpenDisplayEntity, EventEntity):
    """A button event entity for an OpenDisplay device."""

    entity_description: OpenDisplayEventEntityDescription

    @callback
    def _handle_coordinator_update(self) -> None:
        """Fire events for button transitions reported by this coordinator update."""
        if self.coordinator.data is not None:
            for event in self.coordinator.data.button_events:
                if (
                    event.byte_index == self.entity_description.byte_index
                    and event.button_id == self.entity_description.button_id
                    and event.event_type in self.event_types
                ):
                    self._trigger_event(event.event_type)
        self.async_write_ha_state()
