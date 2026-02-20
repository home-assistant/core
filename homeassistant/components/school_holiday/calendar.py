"""Calendar platform for the School Holiday integration."""

from __future__ import annotations

from datetime import date, datetime
import logging

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.const import CONF_COUNTRY, CONF_NAME, CONF_REGION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SchoolHolidayConfigEntry
from .coordinator import SchoolHolidayCoordinator
from .utils import generate_unique_id

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SchoolHolidayConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Setup the School Holiday calendar."""
    coordinator = entry.runtime_data
    country = str(entry.data.get(CONF_COUNTRY))
    region = str(entry.data.get(CONF_REGION))
    name = str(entry.data.get(CONF_NAME))

    async_add_entities(
        [SchoolHolidayCalendarEntity(coordinator, name, country, region)], True
    )


class SchoolHolidayCalendarEntity(
    CoordinatorEntity[SchoolHolidayCoordinator], CalendarEntity
):
    """Representation of the School Holiday calendar."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:school"
    _attr_translation_key = "school_holiday"

    def __init__(
        self,
        coordinator: SchoolHolidayCoordinator,
        name: str | None,
        country: str,
        region: str,
    ) -> None:
        """Initialize the calendar entity."""
        super().__init__(coordinator)
        self._attr_name = name
        self._country = country
        self._region = region
        self._attr_unique_id = generate_unique_id(country, region)

    async def async_update(self) -> None:
        """Update the calendar events from the coordinator."""
        await self.coordinator.async_request_refresh()

    @property
    def events(self) -> list[dict]:
        """Return all school holiday events."""
        return self.coordinator.data or []

    @property
    def event(self) -> CalendarEvent | None:
        """Get the next upcoming school holiday."""
        events = self.coordinator.data or []
        if not events:
            return None

        now = date.today()
        upcoming = [e for e in events if e["end"] > now]

        if upcoming:
            event = upcoming[0]

            return CalendarEvent(
                summary=event["summary"],
                start=event["start"],
                end=event["end"],
                description=event.get("description"),
            )
        return None

    async def async_get_events(
        self, _hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get the school holidays within the specified date range."""
        events = self.coordinator.data or []

        return [
            CalendarEvent(
                summary=event["summary"],
                start=event["start"],
                end=event["end"],
                description=event.get("description"),
            )
            for event in events
            if event["start"] < end_date.date() and event["end"] > start_date.date()
        ]
