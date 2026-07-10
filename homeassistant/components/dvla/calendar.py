"""DVLA calendar platform."""

from datetime import date, datetime
import hashlib
import json
from typing import Any, cast, override
import uuid

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_CALENDARS, CONF_REG_NUMBER, DOMAIN
from .coordinator import DVLACoordinator

CALENDAR_DATE_KEYS: tuple[str, ...] = (
    "taxDueDate",
    "artEndDate",
    "motExpiryDate",
    "dateOfLastV5CIssued",
)

CALENDAR_EVENT_NAMES: dict[str, str] = {
    "taxDueDate": "Tax due date",
    "artEndDate": "Additional rate of tax end date",
    "motExpiryDate": "M.O.T expiry date",
    "dateOfLastV5CIssued": "Date of last V5C issued",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors from a config entry created in the integrations UI."""
    config = entry.runtime_data
    # Update our config to include new repos and remove those that have been removed.
    if entry.options:
        config.update(entry.options)

    reg_number = entry.data[CONF_REG_NUMBER]

    calendars = entry.data.get(CONF_CALENDARS, {})

    coordinator: DVLACoordinator = config["coordinator"]

    sensors = [DVLACalendarSensor(coordinator, reg_number)]

    for calendar in calendars:
        if calendar != "None":
            for sensor in sensors:
                events = sensor.get_events(datetime.today(), reg_number)
                for event in events:
                    await add_to_calendar(hass, calendar, event, entry)

    if "None" in calendars:
        async_add_entities(sensors, update_before_add=True)


async def create_event(hass: HomeAssistant, service_data):
    """Create calendar event."""
    try:
        await hass.services.async_call(
            "calendar",
            "create_event",
            service_data,
            blocking=True,
            return_response=True,
        )
    except ServiceValidationError, HomeAssistantError:
        await hass.services.async_call(
            "calendar",
            "create_event",
            service_data,
            blocking=True,
        )


class DateTimeEncoder(json.JSONEncoder):
    """Encode date time object."""

    @override
    def default(self, o):
        """Encode date time object."""
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return super().default(o)


def generate_uuid_from_json(json_obj: dict[str, Any]) -> str:
    """Generate a UUID from a JSON object."""
    json_string = json.dumps(json_obj, cls=DateTimeEncoder, sort_keys=True)
    sha1_hash = hashlib.sha1(
        json_string.encode("utf-8"), usedforsecurity=False
    ).digest()

    return str(uuid.UUID(bytes=sha1_hash[:16]))


async def get_event_uid(
    hass: HomeAssistant,
    service_data: dict[str, Any],
) -> str | None:
    """Fetch the created event by matching with details in service_data."""
    entity_id = service_data.get("entity_id")
    start_time = service_data.get("start_date")
    end_time = service_data.get("end_date")

    if not isinstance(entity_id, str):
        return None

    try:
        response = await hass.services.async_call(
            "calendar",
            "get_events",
            {
                "entity_id": entity_id,
                "start_date_time": f"{start_time}T00:00:00+0000",
                "end_date_time": f"{end_time}T00:00:00+0000",
            },
            return_response=True,
            blocking=True,
        )
    except ServiceValidationError, HomeAssistantError:
        return None

    events_response = cast(dict[str, Any], response)
    calendar_response = events_response.get(entity_id)

    if not isinstance(calendar_response, dict):
        return None

    events = calendar_response.get("events", [])

    if not isinstance(events, list):
        return None

    for event in events:
        if not isinstance(event, dict):
            continue

        if (
            event.get("summary") == service_data["summary"]
            and str(event.get("description")) == str(service_data["description"])
            and str(event.get("location")) == str(service_data["location"])
        ):
            return generate_uuid_from_json(service_data)

    return None


async def add_to_calendar(
    hass: HomeAssistant,
    calendar: str,
    event: CalendarEvent,
    entry: ConfigEntry,
) -> None:
    """Add an event to the calendar."""

    service_data = {
        "entity_id": calendar,
        "start_date": event.start,
        "end_date": event.end,
        "summary": event.summary,
        "description": f"{event.description}",
        "location": f"{event.location}",
    }

    uid = await get_event_uid(hass, service_data)

    uids = entry.data.get("uids", [])

    if uid not in uids:
        await create_event(hass, service_data)

        created_event_uid = await get_event_uid(hass, service_data)

        if created_event_uid is not None and created_event_uid not in uids:
            uids.append(created_event_uid)

    if uids != entry.data.get("uids", []):
        updated_data = entry.data.copy()
        updated_data["uids"] = uids
        hass.config_entries.async_update_entry(entry, data=updated_data)


class DVLACalendarSensor(CoordinatorEntity[DVLACoordinator], CalendarEntity):
    """Define a DVLA calendar entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DVLACoordinator,
        reg_number: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{reg_number}")},
            manufacturer=DOMAIN.upper(),
            model=coordinator.data.get("make"),
            name=reg_number.upper(),
            configuration_url="https://github.com/jampez77/DVLA-Vehicle-Checker/",
        )
        self._attr_unique_id = reg_number.lower()
        self._attr_name = f"{DOMAIN} - {reg_number}".upper()
        self.reg_number = reg_number

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self.coordinator.data)

    @property
    @override
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        events = self.get_events(datetime.today(), self.reg_number)
        if not events:
            return None
        return sorted(events, key=lambda c: c.start)[0]

    def get_events(self, start_date: datetime, reg_number: str) -> list[CalendarEvent]:
        """Return calendar events."""
        events = []
        for key in CALENDAR_DATE_KEYS:
            raw_value = self.coordinator.data.get(key)
            if not raw_value:
                continue

            try:
                value = date.fromisoformat(raw_value)
            except ValueError:
                continue

            if value >= start_date.date():
                event_name = f"{CALENDAR_EVENT_NAMES[key]} - {reg_number}"
                events.append(CalendarEvent(value, value, event_name))
        return events

    @override
    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        return [
            event
            for event in self.get_events(start_date, self.reg_number)
            if event.start <= end_date.date()
        ]
