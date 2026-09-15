"""Calendar platform for the pretalx integration."""

from datetime import datetime
from typing import override

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import PretalxConfigEntry, PretalxCoordinator, PretalxSession

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PretalxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the pretalx calendar platform."""
    coordinator = entry.runtime_data
    known_rooms: set[int] = set()

    @callback
    def _add_entities() -> None:
        new_rooms = set(coordinator.data.rooms) - known_rooms
        if not new_rooms:
            return
        known_rooms.update(new_rooms)
        async_add_entities(
            PretalxCalendarEntity(coordinator, room_id) for room_id in new_rooms
        )

    _add_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_entities))


def _to_calendar_event(session: PretalxSession) -> CalendarEvent:
    """Convert a pretalx session into a calendar event."""
    return CalendarEvent(
        summary=session.title,
        start=dt_util.as_local(session.start),
        end=dt_util.as_local(session.end),
        description=session.description,
        location=session.room_name,
        uid=session.uid,
    )


class PretalxCalendarEntity(CoordinatorEntity[PretalxCoordinator], CalendarEntity):
    """A calendar entity for a single pretalx room."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PretalxCoordinator, room_id: int) -> None:
        """Initialize the calendar entity."""
        super().__init__(coordinator)
        self._room_id = room_id
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{room_id}"
        self._attr_name = coordinator.data.rooms[room_id].name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=coordinator.data.event_name,
            manufacturer="pretalx",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def _sessions(self) -> list[PretalxSession]:
        """Return the sessions scheduled in this room, ordered by start."""
        return self.coordinator.data.sessions.get(self._room_id, [])

    @property
    @override
    def event(self) -> CalendarEvent | None:
        """Return the current or next upcoming session."""
        now = dt_util.now()
        for session in self._sessions:
            if session.end > now:
                return _to_calendar_event(session)
        return None

    @override
    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return all sessions in a specific time frame."""
        return [
            _to_calendar_event(session)
            for session in self._sessions
            if session.start < end_date and session.end > start_date
        ]
