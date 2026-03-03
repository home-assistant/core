"""Calendar platform for the School Holiday integration."""

from __future__ import annotations

from datetime import date, datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.const import CONF_COUNTRY, CONF_REGION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SchoolHolidayConfigEntry
from .const import CONF_CALENDAR_NAME, DOMAIN, LOGGER
from .coordinator import SchoolHolidayCoordinator
from .utils import get_device_name

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SchoolHolidayConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the School Holiday calendar."""
    LOGGER.debug("Starting calendar setup")
    coordinator = entry.runtime_data
    country = str(entry.data.get(CONF_COUNTRY))
    region = str(entry.data.get(CONF_REGION))
    calendar_name = str(entry.data[CONF_CALENDAR_NAME])

    async_add_entities(
        [
            SchoolHolidayCalendarEntity(
                coordinator, calendar_name, country, region, entry.entry_id
            )
        ],
        True,
    )


class SchoolHolidayCalendarEntity(
    CoordinatorEntity[SchoolHolidayCoordinator], CalendarEntity
):
    """Representation of the School Holiday calendar."""

    _attr_icon = "mdi:calendar-check"

    def __init__(
        self,
        coordinator: SchoolHolidayCoordinator,
        calendar_name: str,
        country: str,
        region: str,
        entry_id: str,
    ) -> None:
        """Initialize the calendar entity."""
        super().__init__(coordinator)
        self._attr_name = calendar_name
        self._country = country
        self._region = region
        self._attr_unique_id = f"{entry_id}_calendar"

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            name=get_device_name(country, region),
        )

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
            # Select the event with the earliest start date.
            event = min(upcoming, key=lambda e: e["start"])

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
