"""Support for SFR Box event entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sfrbox_api.models import VoipCallHistoryCall, VoipCallHistoryList

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SFRConfigEntry, SFRDataUpdateCoordinator, SystemInfo
from .entity import SFRCoordinatorEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SFRBoxEventEntityDescription[_T](EventEntityDescription):
    """Description for SFR Box event."""


VOIP_CALLHISTORYLIST_EVENTS: tuple[
    SFRBoxEventEntityDescription[VoipCallHistoryList], ...
] = (
    SFRBoxEventEntityDescription[VoipCallHistoryList](
        key="callhistorylist",
        translation_key="voip_callhistorylist",
        event_types=["incoming", "outgoing", "missed"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SFRConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    data = entry.runtime_data
    system_info = data.system.data
    if TYPE_CHECKING:
        assert system_info is not None

    if data.voip_callhistorylist is not None:
        entities: list[SFRBoxEvent] = [
            SFRBoxEvent(data.voip_callhistorylist, description, system_info)
            for description in VOIP_CALLHISTORYLIST_EVENTS
        ]
        async_add_entities(entities)


class SFRBoxEvent(SFRCoordinatorEntity[VoipCallHistoryList], EventEntity):
    """SFR Box event entity."""

    entity_description: SFRBoxEventEntityDescription[VoipCallHistoryList]
    _attr_should_poll = False
    _attr_event_types: list[str]

    def __init__(
        self,
        coordinator: SFRDataUpdateCoordinator[VoipCallHistoryList],
        description: SFRBoxEventEntityDescription[VoipCallHistoryList],
        system_info: SystemInfo,
    ) -> None:
        """Initialize the event entity."""
        super().__init__(coordinator, description, system_info)
        self._previous_calls: set[str] = set()
        self._attr_event_types = description.event_types or []

    async def async_added_to_hass(self) -> None:
        """Handle entity added to Home Assistant."""
        await super().async_added_to_hass()
        # Initialize with current calls to avoid firing events on first load
        if self.coordinator.data:
            self._previous_calls = {
                self._call_id(call) for call in self.coordinator.data.calls or []
            }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update - fire events for new calls."""

        if not self.coordinator.data or not self.coordinator.data.calls:
            return

        current_calls = self.coordinator.data.calls
        current_call_ids = {self._call_id(call) for call in current_calls}

        # Find new calls
        new_call_ids = current_call_ids - self._previous_calls

        # Fire events for each new call
        for call in current_calls:
            call_id = self._call_id(call)
            if call_id in new_call_ids:
                self._trigger_event(
                    self._get_event_type(call),
                    event_attributes=self._call_to_attributes(call),
                )

        # Update previous calls for next update
        self._previous_calls = current_call_ids
        # Write state to update timestamp
        self.async_write_ha_state()

    @staticmethod
    def _call_id(call: VoipCallHistoryCall) -> str:
        """Generate unique call identifier."""
        return f"{call.date}_{call.number}_{call.direction}"

    @staticmethod
    def _get_event_type(call: VoipCallHistoryCall) -> str:
        """Get event type from call."""
        if call.length == -1:
            return "missed"
        return call.direction

    @staticmethod
    def _call_to_attributes(call: VoipCallHistoryCall) -> dict[str, Any]:
        """Convert call to event attributes."""
        return {
            "type": call.type,
            "direction": call.direction,
            "number": call.number,
            "length": call.length,
            "date": call.date,
        }
