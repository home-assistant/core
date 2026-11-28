"""Event entity for issued and updated GeoSphere Austria weather warnings."""

from typing import override

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import GeoSphereConfigEntry, GeoSphereUpdateCoordinator
from .entity import GeoSphereEntity
from .warnings import serialize_warning, sort_warnings

PARALLEL_UPDATES = 0

EVENT_ISSUED = "issued"
EVENT_UPDATED = "updated"

WARNING_EVENT = EventEntityDescription(
    key="warning",
    translation_key="warning",
    event_types=[EVENT_ISSUED, EVENT_UPDATED],
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GeoSphereConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the event entity."""
    async_add_entities([GeoSphereWarningEvent(entry.runtime_data, WARNING_EVENT)])


class GeoSphereWarningEvent(GeoSphereEntity, EventEntity):
    """Event entity firing when a warning is issued or updated."""

    def __init__(
        self,
        coordinator: GeoSphereUpdateCoordinator,
        description: EventEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, description)
        # Warnings present at setup are already known and do not fire an event.
        self._known_changes = self._current_changes()

    def _current_changes(self) -> dict[tuple[int, int], int]:
        """Return the change ID of every published warning course."""
        # Include expired courses, so extending one reports an update.
        return {
            (warning.warning_id, warning.course_id): warning.change_id
            for warning in self.coordinator.data.location_warnings.warnings
        }

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Fire an event for every new or changed warning."""
        # Publish the recovered state first, so automations ignoring transitions
        # from unavailable do not miss the first event after a failed update.
        super()._handle_coordinator_update()
        data = self.coordinator.data
        for warning in sort_warnings((*data.active_warnings, *data.advance_warnings)):
            known_change = self._known_changes.get(
                (warning.warning_id, warning.course_id)
            )
            if known_change == warning.change_id:
                continue
            self._trigger_event(
                EVENT_ISSUED if known_change is None else EVENT_UPDATED,
                serialize_warning(warning),
            )
            self.async_write_ha_state()
        self._known_changes = self._current_changes()
