"""Support for event entities."""

from __future__ import annotations

from togrill_bluetooth.packets import Packet, PacketA5Notify

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from . import ToGrillConfigEntry
from .const import CONF_PROBE_COUNT
from .coordinator import ToGrillCoordinator
from .entity import ToGrillEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ToGrillConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up event platform."""
    async_add_entities(
        ToGrillEventEntity(config_entry.runtime_data, probe_number=probe_number)
        for probe_number in range(1, config_entry.data[CONF_PROBE_COUNT] + 1)
    )


class ToGrillEventEntity(ToGrillEntity, EventEntity):
    """Representation of a Hue Event entity from a button resource."""

    def __init__(self, coordinator: ToGrillCoordinator, probe_number: int) -> None:
        """Initialize the entity."""
        super().__init__(coordinator=coordinator, probe_number=probe_number)

        self._attr_translation_key = "event"
        self._attr_translation_placeholders = {"probe_number": f"{probe_number}"}
        self._attr_unique_id = f"{coordinator.address}_{probe_number}"
        self._probe_number = probe_number

        self._attr_event_types: list[str] = [
            slugify(event.name) for event in PacketA5Notify.Message
        ]

        self.async_on_remove(coordinator.async_add_packet_listener(self._handle_event))

    @callback
    def _handle_event(self, packet: Packet) -> None:
        if not isinstance(packet, PacketA5Notify):
            return

        try:
            message = PacketA5Notify.Message(packet.message)
        except ValueError:
            return

        if packet.probe != self._probe_number:
            return

        self._trigger_event(message.name.lower())
