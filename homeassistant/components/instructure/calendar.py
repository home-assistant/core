import datetime
from datetime import timezone
from homeassistant.core import HomeAssistant
from homeassistant.components.calendar import (
    ENTITY_ID_FORMAT,
    CalendarEntity,
    CalendarEvent,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import generate_entity_id

from .coordinator import CanvasUpdateCoordinator
from .const import DOMAIN, ASSIGNMENTS_KEY


class CanvasCalendarEntity(CalendarEntity):
    """A calendar entity for Canvas assignments"""

    def __init__(self, hass, coordinator, entity_id):
        self.hass = hass
        self.coordinator = coordinator
        self.entity_id = entity_id
        self._attr_unique_id = ""
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "calendar_canvas_assignments")},
            entry_type=DeviceEntryType.SERVICE,
            name="Assignment Calendar",
            manufacturer="Canvas",
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        assignments = self.get_assignments_with_due_date()

        current_time = datetime.datetime.now(timezone.utc)

        next_assignment = min(
            (
                item
                for item in assignments
                if self.parse_date(item["due_at"]) > current_time
            ),
            key=lambda item: self.parse_date(item["due_at"]),
            default=None,
        )

        return CalendarEvent(
            start=self.parse_date(next_assignment["due_at"]),
            end=self.parse_date(next_assignment["due_at"])
            + datetime.timedelta(hours=1),
            summary=next_assignment["name"],
            description=next_assignment["html_url"],
        )

    def get_assignments_with_due_date(self):
        assignments = self.coordinator.data[ASSIGNMENTS_KEY].values()
        return [i for i in assignments if i["due_at"]]

    def parse_date(self, date_str):
        return datetime.datetime.fromisoformat(date_str)

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        assignments = self.get_assignments_with_due_date()
        filtered_assignments = [
            item
            for item in assignments
            if start_date <= self.parse_date(item["due_at"]) <= end_date
        ]

        event_list = []
        for assignment in filtered_assignments:
            event_list.append(
                CalendarEvent(
                    start=self.parse_date(assignment["due_at"]),
                    end=self.parse_date(assignment["due_at"])
                    + datetime.timedelta(hours=1),
                    summary=assignment["name"],
                    description=assignment["html_url"],
                )
            )

        return event_list


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Canvas sensor based on a config entry"""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    canvas_calendar_entity = CanvasCalendarEntity(
        hass,
        coordinator,
        generate_entity_id(ENTITY_ID_FORMAT, "canvas_calendar_assignments", hass=hass),
    )

    async_add_entities([canvas_calendar_entity])
