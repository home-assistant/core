"""Support for Google Calendar event device sensors."""
from __future__ import annotations

from collections.abc import Iterable
import dataclasses
import datetime
from http import HTTPStatus
import logging
import re
from typing import Any, cast, final

from aiohttp import web
import voluptuous as vol

from homeassistant.components import frontend, http, websocket_api
from homeassistant.components.websocket_api import ERR_NOT_SUPPORTED
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
    time_period_str,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.template import DATE_STR_FORMAT
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt

from .const import (
    CONF_EVENT,
    EVENT_DESCRIPTION,
    EVENT_END,
    EVENT_RECURRENCE_ID,
    EVENT_RECURRENCE_RANGE,
    EVENT_RRULE,
    EVENT_START,
    EVENT_SUMMARY,
    EVENT_UID,
    CalendarEntityFeature,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "calendar"
ENTITY_ID_FORMAT = DOMAIN + ".{}"
SCAN_INTERVAL = datetime.timedelta(seconds=60)

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track states and offer events for calendars."""
    component = hass.data[DOMAIN] = EntityComponent[CalendarEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    hass.http.register_view(CalendarListView(component))
    hass.http.register_view(CalendarEventView(component))

    frontend.async_register_built_in_panel(
        hass, "calendar", "calendar", "hass:calendar"
    )

    websocket_api.async_register_command(hass, handle_calendar_event_create)
    websocket_api.async_register_command(hass, handle_calendar_event_delete)

    await component.async_setup(config)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[CalendarEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[CalendarEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


def get_date(date: dict[str, Any]) -> datetime.datetime:
    """Get the dateTime from date or dateTime as a local."""
    if "date" in date:
        parsed_date = dt.parse_date(date["date"])
        assert parsed_date
        return dt.start_of_local_day(
            datetime.datetime.combine(parsed_date, datetime.time.min)
        )
    parsed_datetime = dt.parse_datetime(date["dateTime"])
    assert parsed_datetime
    return dt.as_local(parsed_datetime)


@dataclasses.dataclass
class CalendarEvent:
    """An event on a calendar."""

    start: datetime.date | datetime.datetime
    end: datetime.date | datetime.datetime
    summary: str
    description: str | None = None
    location: str | None = None

    uid: str | None = None
    recurrence_id: str | None = None
    rrule: str | None = None

    @property
    def start_datetime_local(self) -> datetime.datetime:
        """Return event start time as a local datetime."""
        return _get_datetime_local(self.start)

    @property
    def end_datetime_local(self) -> datetime.datetime:
        """Return event end time as a local datetime."""
        return _get_datetime_local(self.end)

    @property
    def all_day(self) -> bool:
        """Return true if the event is an all day event."""
        return not isinstance(self.start, datetime.datetime)

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the event."""
        return {
            **dataclasses.asdict(self, dict_factory=_event_dict_factory),
            "all_day": self.all_day,
        }


def _event_dict_factory(obj: Iterable[tuple[str, Any]]) -> dict[str, str]:
    """Convert CalendarEvent dataclass items to dictionary of attributes."""
    result: dict[str, str] = {}
    for name, value in obj:
        if isinstance(value, (datetime.datetime, datetime.date)):
            result[name] = value.isoformat()
        elif value is not None:
            result[name] = str(value)
    return result


def _api_event_dict_factory(obj: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    """Convert CalendarEvent dataclass items to the API format."""
    result: dict[str, Any] = {}
    for name, value in obj:
        if isinstance(value, datetime.datetime):
            result[name] = {"dateTime": dt.as_local(value).isoformat()}
        elif isinstance(value, datetime.date):
            result[name] = {"date": value.isoformat()}
        else:
            result[name] = value
    return result


def _get_datetime_local(
    dt_or_d: datetime.datetime | datetime.date,
) -> datetime.datetime:
    """Convert a calendar event date/datetime to a datetime if needed."""
    if isinstance(dt_or_d, datetime.datetime):
        return dt.as_local(dt_or_d)
    return dt.start_of_local_day(dt_or_d)


def _get_api_date(dt_or_d: datetime.datetime | datetime.date) -> dict[str, str]:
    """Convert a calendar event date/datetime to a datetime if needed."""
    if isinstance(dt_or_d, datetime.datetime):
        return {"dateTime": dt.as_local(dt_or_d).isoformat()}
    return {"date": dt_or_d.isoformat()}


def extract_offset(summary: str, offset_prefix: str) -> tuple[str, datetime.timedelta]:
    """Extract the offset from the event summary.

    Return a tuple with the updated event summary and offset time.
    """
    # check if we have an offset tag in the message
    # time is HH:MM or MM
    reg = f"{offset_prefix}([+-]?[0-9]{{0,2}}(:[0-9]{{0,2}})?)"
    search = re.search(reg, summary)
    if search and search.group(1):
        time = search.group(1)
        if ":" not in time:
            if time[0] == "+" or time[0] == "-":
                time = f"{time[0]}0:{time[1:]}"
            else:
                time = f"0:{time}"

        offset_time = time_period_str(time)
        summary = (summary[: search.start()] + summary[search.end() :]).strip()
        return (summary, offset_time)
    return (summary, datetime.timedelta())


def is_offset_reached(
    start: datetime.datetime, offset_time: datetime.timedelta
) -> bool:
    """Have we reached the offset time specified in the event title."""
    if offset_time == datetime.timedelta():
        return False
    return start + offset_time <= dt.now(start.tzinfo)


class CalendarEntity(Entity):
    """Base class for calendar event entities."""

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        raise NotImplementedError()

    @final
    @property
    def state_attributes(self) -> dict[str, Any] | None:
        """Return the entity state attributes."""
        if (event := self.event) is None:
            return None

        return {
            "message": event.summary,
            "all_day": event.all_day,
            "start_time": event.start_datetime_local.strftime(DATE_STR_FORMAT),
            "end_time": event.end_datetime_local.strftime(DATE_STR_FORMAT),
            "location": event.location if event.location else "",
            "description": event.description if event.description else "",
        }

    @final
    @property
    def state(self) -> str:
        """Return the state of the calendar event."""
        if (event := self.event) is None:
            return STATE_OFF

        now = dt.now()

        if event.start_datetime_local <= now < event.end_datetime_local:
            return STATE_ON

        return STATE_OFF

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        raise NotImplementedError()

    async def async_create_event(self, **kwargs: Any) -> dict[str, Any]:
        """Add a new event to calendar."""
        raise NotImplementedError()

    async def async_delete_event(
        self,
        uid: str,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Delete an event on the calendar."""
        raise NotImplementedError()


class CalendarEventView(http.HomeAssistantView):
    """View to retrieve calendar content."""

    url = "/api/calendars/{entity_id}"
    name = "api:calendars:calendar"

    def __init__(self, component: EntityComponent[CalendarEntity]) -> None:
        """Initialize calendar view."""
        self.component = component

    async def get(self, request: web.Request, entity_id: str) -> web.Response:
        """Return calendar events."""
        if not (entity := self.component.get_entity(entity_id)) or not isinstance(
            entity, CalendarEntity
        ):
            return web.Response(status=HTTPStatus.BAD_REQUEST)

        start = request.query.get("start")
        end = request.query.get("end")
        if start is None or end is None:
            return web.Response(status=HTTPStatus.BAD_REQUEST)
        try:
            start_date = dt.parse_datetime(start)
            end_date = dt.parse_datetime(end)
        except (ValueError, AttributeError):
            return web.Response(status=HTTPStatus.BAD_REQUEST)
        if start_date is None or end_date is None:
            return web.Response(status=HTTPStatus.BAD_REQUEST)

        try:
            calendar_event_list = await entity.async_get_events(
                request.app["hass"], start_date, end_date
            )
        except HomeAssistantError as err:
            return self.json_message(
                f"Error reading events: {err}", HTTPStatus.INTERNAL_SERVER_ERROR
            )

        return self.json(
            [
                dataclasses.asdict(event, dict_factory=_api_event_dict_factory)
                for event in calendar_event_list
            ]
        )


class CalendarListView(http.HomeAssistantView):
    """View to retrieve calendar list."""

    url = "/api/calendars"
    name = "api:calendars"

    def __init__(self, component: EntityComponent[CalendarEntity]) -> None:
        """Initialize calendar view."""
        self.component = component

    async def get(self, request: web.Request) -> web.Response:
        """Retrieve calendar list."""
        hass = request.app["hass"]
        calendar_list: list[dict[str, str]] = []

        for entity in self.component.entities:
            state = hass.states.get(entity.entity_id)
            calendar_list.append({"name": state.name, "entity_id": entity.entity_id})

        return self.json(sorted(calendar_list, key=lambda x: cast(str, x["name"])))


def _get_calendar_entity(hass: HomeAssistant, entity_id: str) -> CalendarEntity:
    if (component := hass.data.get("calendar")) is None:
        raise HomeAssistantError("Calendar integration not set up")

    if (entity := component.get_entity(entity_id)) is None or not isinstance(
        entity, CalendarEntity
    ):
        raise HomeAssistantError(f"Calendar entity not found: {entity_id}")
    return entity


@websocket_api.websocket_command(
    {
        vol.Required("type"): "calendar/event/create",
        vol.Required("entity_id"): cv.entity_id,
        vol.Required(CONF_EVENT): {
            vol.Required(EVENT_START): vol.Any(cv.date, cv.datetime),
            vol.Required(EVENT_END): vol.Any(cv.date, cv.datetime),
            vol.Required(EVENT_SUMMARY): cv.string,
            vol.Optional(EVENT_DESCRIPTION): cv.string,
            vol.Optional(EVENT_RRULE): cv.string,
        },
    }
)
@websocket_api.async_response
async def handle_calendar_event_create(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle creation of a calendar event."""
    try:
        entity = _get_calendar_entity(hass, msg["entity_id"])
    except HomeAssistantError as ex:
        connection.send_error(msg["id"], "failed", str(ex))
        return

    if (
        not entity.supported_features
        or not entity.supported_features & CalendarEntityFeature.MUTABLE
    ):
        connection.send_message(
            websocket_api.error_message(
                msg["id"], ERR_NOT_SUPPORTED, "Calendar does not support event creation"
            )
        )
        return

    try:
        result = await entity.async_create_event(**msg[CONF_EVENT])
    except HomeAssistantError as ex:
        connection.send_error(msg["id"], "failed", str(ex))
    else:
        connection.send_result(msg["id"], {EVENT_UID: result.get(EVENT_UID)})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "calendar/event/delete",
        vol.Required("entity_id"): cv.entity_id,
        vol.Required(EVENT_UID): cv.string,
        vol.Optional(EVENT_RECURRENCE_ID): cv.string,
        vol.Optional(EVENT_RECURRENCE_RANGE): cv.string,
    }
)
@websocket_api.async_response
async def handle_calendar_event_delete(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle delete of a calendar event."""

    try:
        entity = _get_calendar_entity(hass, msg["entity_id"])
    except HomeAssistantError as ex:
        connection.send_error(msg["id"], "failed", str(ex))
        return

    if (
        not entity.supported_features
        or not entity.supported_features & CalendarEntityFeature.MUTABLE
    ):
        connection.send_message(
            websocket_api.error_message(
                msg["id"], ERR_NOT_SUPPORTED, "Calendar does not support event deletion"
            )
        )
        return

    try:
        await entity.async_delete_event(
            msg[EVENT_UID],
            recurrence_id=msg.get(EVENT_RECURRENCE_ID),
            recurrence_range=msg.get(EVENT_RECURRENCE_RANGE),
        )
    except (HomeAssistantError, ValueError) as ex:
        _LOGGER.error("Error handling Calendar Event call: %s", ex)
        connection.send_error(msg["id"], "failed", str(ex))
    else:
        connection.send_result(msg["id"])
