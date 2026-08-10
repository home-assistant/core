"""Support for Gatus event entities."""

from typing import override

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import GatusConfigEntry, GatusDataUpdateCoordinator
from .entity import GatusEndpointEntity

PARALLEL_UPDATES = 0

EVENT_TYPES = ["start", "healthy", "unhealthy", "resolved"]

EVENT_DESCRIPTION = EventEntityDescription(
    key="status_event",
    translation_key="status_event",
    event_types=EVENT_TYPES,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GatusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Gatus event entities based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        GatusEndpointEvent(coordinator, entry, endpoint_key, EVENT_DESCRIPTION)
        for endpoint_key in coordinator.data
    )


class GatusEndpointEvent(GatusEndpointEntity, EventEntity):
    """Representation of a Gatus endpoint event entity."""

    entity_description: EventEntityDescription

    def __init__(
        self,
        coordinator: GatusDataUpdateCoordinator,
        entry: GatusConfigEntry,
        endpoint_key: str,
        description: EventEntityDescription,
    ) -> None:
        """Initialize the event entity."""
        super().__init__(coordinator, entry, endpoint_key)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{endpoint_key}_{description.key}"
        self._last_event_timestamp: str | None = None

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        events = self.endpoint_data.events
        if events:
            latest_event = events[-1]
            if latest_event.timestamp != self._last_event_timestamp:
                self._last_event_timestamp = latest_event.timestamp
                event_type = latest_event.type.lower()
                if event_type in EVENT_TYPES:
                    self._trigger_event(event_type)

        super()._handle_coordinator_update()
