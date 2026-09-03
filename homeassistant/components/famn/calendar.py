"""Calendar platform for the Famn integration."""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, override

from famn_sdk import ApiError, CalendarEvent as FamnCalendarEvent

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import FamnCalendarsCoordinator, FamnConfigEntry
from .entity import famn_device_info

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FamnConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the calendar platform from a config entry."""
    coordinator = entry.runtime_data.calendars
    known_calendars: set[str] = set()

    @callback
    def add_entities() -> None:
        """Add calendar entities for calendars that appeared in Famn."""
        if new_calendars := set(coordinator.data) - known_calendars:
            async_add_entities(
                FamnCalendarEntity(coordinator, calendar_id)
                for calendar_id in new_calendars
            )
            known_calendars.update(new_calendars)

    coordinator.async_add_listener(add_entities)
    add_entities()


def _event_end(event: FamnCalendarEvent) -> datetime:
    """Return when an occurrence ends, mirroring the server's padding."""
    if event.end_date_time is not None:
        return event.end_date_time
    if event.all_day:
        return event.start_date_time + timedelta(days=1)
    return event.start_date_time + timedelta(minutes=1)


def _to_ha_event(event: FamnCalendarEvent) -> CalendarEvent:
    """Map a Famn occurrence onto a Home Assistant calendar event."""
    uid = str(event.id) if event.id is not None else None
    recurrence_id = (
        event.recurrence_id.isoformat() if event.recurrence_id is not None else None
    )

    if event.all_day:
        # All-day occurrences are stored as the local-midnight instant of
        # the intended day in the event's timezone; the DATE is only correct
        # when read back in that timezone.
        time_zone = (
            dt_util.get_time_zone(event.time_zone) if event.time_zone else None
        ) or dt_util.UTC
        start_date = event.start_date_time.astimezone(time_zone).date()
        end_date = _event_end(event).astimezone(time_zone).date()
        if end_date <= start_date:
            end_date = start_date + timedelta(days=1)
        return CalendarEvent(
            summary=event.title,
            start=start_date,
            end=end_date,
            description=event.description,
            location=event.location,
            uid=uid,
            recurrence_id=recurrence_id,
        )

    return CalendarEvent(
        summary=event.title,
        start=event.start_date_time,
        end=_event_end(event),
        description=event.description,
        location=event.location,
        uid=uid,
        recurrence_id=recurrence_id,
    )


class FamnCalendarEntity(CoordinatorEntity[FamnCalendarsCoordinator], CalendarEntity):
    """A calendar entity for one Famn calendar.

    Device tokens can only read calendars, so the entity exposes no event
    creation or modification.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: FamnCalendarsCoordinator, calendar_id: str) -> None:
        """Initialize the calendar entity."""
        super().__init__(coordinator)

        unique_id = coordinator.config_entry.unique_id
        if TYPE_CHECKING:
            assert unique_id is not None

        self._key = calendar_id
        self._attr_unique_id = f"{unique_id}_{calendar_id}"
        self._attr_name = coordinator.data[calendar_id].calendar.name
        self._attr_device_info = famn_device_info(coordinator.config_entry)

    @property
    @override
    def available(self) -> bool:
        """Return if the underlying Famn calendar still exists."""
        return super().available and self._key in self.coordinator.data

    @property
    @override
    def event(self) -> CalendarEvent | None:
        """Return the current or next upcoming occurrence."""
        now = dt_util.utcnow()
        for famn_event in self.coordinator.data[self._key].upcoming:
            if _event_end(famn_event) > now:
                return _to_ha_event(famn_event)
        return None

    @override
    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return the occurrences within a time range."""
        try:
            events = await self.coordinator.async_get_events_between(
                self._key, start_date, end_date
            )
        except ApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="calendar_events_failed",
            ) from err
        return [_to_ha_event(event) for event in events]
