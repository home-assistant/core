import datetime
from homeassistant.core import HomeAssistant
from homeassistant.components.calendar import ENTITY_ID_FORMAT, CalendarEntity, CalendarEvent
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
            name="Calendar Canvas Assignments",
            manufacturer="Canvas"
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        assignments = self.get_assignments()

        current_time = datetime.datetime.now()
        return min((item for item in assignments if self.parse_date(item["due_at"]) > current_time),
               key=lambda item: self.parse_date(item["due_at"]), default=None)

    def get_assignments(self):
        return self.coordinator.data[ASSIGNMENTS_KEY].values()

    def parse_date(self, date_str):
        return datetime.datetime.fromisoformat(date_str)

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        assignments = self.get_assignments()
        filtered_assignments = [item for item in assignments if start_date <= self.parse_date(item["due_at"]) <= end_date]

        event_list = []
        for assignment in filtered_assignments:
            event = CalendarEvent(
                start=self.parse_date(assignment["due_at"]),
                end=self.parse_date(assignment["due_at"]),
                summary=assignment["name"],
                description=assignment["description"]
            )
            event_list.append(event)

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
        generate_entity_id(
            ENTITY_ID_FORMAT,
            "canvas_calendar_assignments",
            hass=hass
        )
    )

    async_add_entities([canvas_calendar_entity])