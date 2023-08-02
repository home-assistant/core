"""Support for Google Calendar event device sensors."""
from __future__ import annotations

from collections.abc import Callable, Iterable
import dataclasses
import datetime
from http import HTTPStatus
from itertools import groupby
import logging
import re
from typing import Any, Final, cast, final

from aiohttp import web
from dateutil.rrule import rrulestr
import voluptuous as vol

from homeassistant.components import frontend, http, websocket_api
from homeassistant.components.websocket_api import ERR_NOT_FOUND, ERR_NOT_SUPPORTED
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
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
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonValueType

from .const import (
    CONF_EVENT,
    EVENT_DESCRIPTION,
    EVENT_DURATION,
    EVENT_END,
    EVENT_END_DATE,
    EVENT_END_DATETIME,
    EVENT_IN,
    EVENT_IN_DAYS,
    EVENT_IN_WEEKS,
    EVENT_LOCATION,
    EVENT_RECURRENCE_ID,
    EVENT_RECURRENCE_RANGE,
    EVENT_RRULE,
    EVENT_START,
    EVENT_START_DATE,
    EVENT_START_DATETIME,
    EVENT_SUMMARY,
    EVENT_TIME_FIELDS,
    EVENT_TYPES,
    EVENT_UID,
    LIST_EVENT_FIELDS,
    CalendarEntityFeature,
)

# mypy: disallow-any-generics

_LOGGER = logging.getLogger(__name__)

DOMAIN = "calendar"
ENTITY_ID_FORMAT = DOMAIN + ".{}"
SCAN_INTERVAL = datetime.timedelta(seconds=60)

# Don't support rrules more often than daily
VALID_FREQS = {"DAILY", "WEEKLY", "MONTHLY", "YEARLY"}

# Ensure events created in Home Assistant have a positive duration
MIN_NEW_EVENT_DURATION = datetime.timedelta(seconds=1)

# Events must have a non-negative duration e.g. Google Calendar can create zero
# duration events in the UI.
MIN_EVENT_DURATION = datetime.timedelta(seconds=0)


def _has_timezone(*keys: Any) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Assert that all datetime values have a timezone."""

    def validate(obj: dict[str, Any]) -> dict[str, Any]:
        """Validate that all datetime values have a timezone."""
        for k in keys:
            if (
                (value := obj.get(k))
                and isinstance(value, datetime.datetime)
                and value.tzinfo is None
            ):
                raise vol.Invalid("Expected all values to have a timezone")
        return obj

    return validate


def _has_consistent_timezone(*keys: Any) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Verify that all datetime values have a consistent timezone."""

    def validate(obj: dict[str, Any]) -> dict[str, Any]:
        """Test that all keys that are datetime values have the same timezone."""
        tzinfos = []
        for key in keys:
            if not (value := obj.get(key)) or not isinstance(value, datetime.datetime):
                return obj
            tzinfos.append(value.tzinfo)
        uniq_values = groupby(tzinfos)
        if len(list(uniq_values)) > 1:
            raise vol.Invalid("Expected all values to have the same timezone")
        return obj

    return validate


def _as_local_timezone(*keys: Any) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Convert all datetime values to the local timezone."""

    def validate(obj: dict[str, Any]) -> dict[str, Any]:
        """Convert all keys that are datetime values to local timezone."""
        for k in keys:
            if (value := obj.get(k)) and isinstance(value, datetime.datetime):
                obj[k] = dt_util.as_local(value)
        return obj

    return validate


def _has_min_duration(
    start_key: str, end_key: str, min_duration: datetime.timedelta
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Verify that the time span between start and end has a minimum duration."""

    def validate(obj: dict[str, Any]) -> dict[str, Any]:
        if (start := obj.get(start_key)) and (end := obj.get(end_key)):
            duration = end - start
            if duration < min_duration:
                raise vol.Invalid(
                    f"Expected minimum event duration of {min_duration} ({start}, {end})"
                )
        return obj

    return validate


def _has_same_type(*keys: Any) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Verify that all values are of the same type."""

    def validate(obj: dict[str, Any]) -> dict[str, Any]:
        """Test that all keys in the dict have values of the same type."""
        uniq_values = groupby(type(obj[k]) for k in keys)
        if len(list(uniq_values)) > 1:
            raise vol.Invalid(f"Expected all values to be the same type: {keys}")
        return obj

    return validate


def _validate_rrule(value: Any) -> str:
    """Validate a recurrence rule string."""
    if value is None:
        raise vol.Invalid("rrule value is None")

    if not isinstance(value, str):
        raise vol.Invalid("rrule value expected a string")

    try:
        rrulestr(value)
    except ValueError as err:
        raise vol.Invalid(f"Invalid rrule '{value}': {err}") from err

    # Example format: FREQ=DAILY;UNTIL=...
    rule_parts = dict(s.split("=", 1) for s in value.split(";"))
    if not (freq := rule_parts.get("FREQ")):
        raise vol.Invalid("rrule did not contain FREQ")

    if freq not in VALID_FREQS:
        raise vol.Invalid(f"Invalid frequency for rule: {value}")

    return str(value)


CREATE_EVENT_SERVICE = "create_event"
CREATE_EVENT_SCHEMA = vol.All(
    cv.has_at_least_one_key(EVENT_START_DATE, EVENT_START_DATETIME, EVENT_IN),
    cv.has_at_most_one_key(EVENT_START_DATE, EVENT_START_DATETIME, EVENT_IN),
    cv.make_entity_service_schema(
        {
            vol.Required(EVENT_SUMMARY): cv.string,
            vol.Optional(EVENT_DESCRIPTION, default=""): cv.string,
            vol.Optional(EVENT_LOCATION): cv.string,
            vol.Inclusive(
                EVENT_START_DATE, "dates", "Start and end dates must both be specified"
            ): cv.date,
            vol.Inclusive(
                EVENT_END_DATE, "dates", "Start and end dates must both be specified"
            ): cv.date,
            vol.Inclusive(
                EVENT_START_DATETIME,
                "datetimes",
                "Start and end datetimes must both be specified",
            ): cv.datetime,
            vol.Inclusive(
                EVENT_END_DATETIME,
                "datetimes",
                "Start and end datetimes must both be specified",
            ): cv.datetime,
            vol.Optional(EVENT_IN): vol.Schema(
                {
                    vol.Exclusive(EVENT_IN_DAYS, EVENT_TYPES): cv.positive_int,
                    vol.Exclusive(EVENT_IN_WEEKS, EVENT_TYPES): cv.positive_int,
                }
            ),
        },
    ),
    _has_consistent_timezone(EVENT_START_DATETIME, EVENT_END_DATETIME),
    _as_local_timezone(EVENT_START_DATETIME, EVENT_END_DATETIME),
    _has_min_duration(EVENT_START_DATE, EVENT_END_DATE, MIN_NEW_EVENT_DURATION),
    _has_min_duration(EVENT_START_DATETIME, EVENT_END_DATETIME, MIN_NEW_EVENT_DURATION),
)

WEBSOCKET_EVENT_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(EVENT_START): vol.Any(cv.date, cv.datetime),
            vol.Required(EVENT_END): vol.Any(cv.date, cv.datetime),
            vol.Required(EVENT_SUMMARY): cv.string,
            vol.Optional(EVENT_DESCRIPTION): cv.string,
            vol.Optional(EVENT_LOCATION): cv.string,
            vol.Optional(EVENT_RRULE): _validate_rrule,
        },
        _has_same_type(EVENT_START, EVENT_END),
        _has_consistent_timezone(EVENT_START, EVENT_END),
        _as_local_timezone(EVENT_START, EVENT_END),
        _has_min_duration(EVENT_START, EVENT_END, MIN_NEW_EVENT_DURATION),
    )
)

# Validation for the CalendarEvent dataclass
CALENDAR_EVENT_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required("start"): vol.Any(cv.date, cv.datetime),
            vol.Required("end"): vol.Any(cv.date, cv.datetime),
            vol.Required(EVENT_SUMMARY): cv.string,
            vol.Optional(EVENT_RRULE): _validate_rrule,
        },
        _has_same_type("start", "end"),
        _has_timezone("start", "end"),
        _as_local_timezone("start", "end"),
        _has_min_duration("start", "end", MIN_EVENT_DURATION),
    ),
    extra=vol.ALLOW_EXTRA,
)

SERVICE_LIST_EVENTS: Final = "list_events"
SERVICE_LIST_EVENTS_SCHEMA: Final = vol.All(
    cv.has_at_least_one_key(EVENT_END_DATETIME, EVENT_DURATION),
    cv.has_at_most_one_key(EVENT_END_DATETIME, EVENT_DURATION),
    cv.make_entity_service_schema(
        {
            vol.Optional(EVENT_START_DATETIME): cv.datetime,
            vol.Optional(EVENT_END_DATETIME): cv.datetime,
            vol.Optional(EVENT_DURATION): vol.All(
                cv.time_period, cv.positive_timedelta
            ),
        }
    ),
)


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
    websocket_api.async_register_command(hass, handle_calendar_event_update)

    component.async_register_entity_service(
        CREATE_EVENT_SERVICE,
        CREATE_EVENT_SCHEMA,
        async_create_event,
        required_features=[CalendarEntityFeature.CREATE_EVENT],
    )
    component.async_register_entity_service(
        SERVICE_LIST_EVENTS,
        SERVICE_LIST_EVENTS_SCHEMA,
        async_list_events_service,
        supports_response=SupportsResponse.ONLY,
    )
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
        parsed_date = dt_util.parse_date(date["date"])
        assert parsed_date
        return dt_util.start_of_local_day(
            datetime.datetime.combine(parsed_date, datetime.time.min)
        )
    parsed_datetime = dt_util.parse_datetime(date["dateTime"])
    assert parsed_datetime
    return dt_util.as_local(parsed_datetime)


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

    def __post_init__(self) -> None:
        """Perform validation on the CalendarEvent."""

        def skip_none(obj: Iterable[tuple[str, Any]]) -> dict[str, str]:
            return {k: v for k, v in obj if v is not None}

        try:
            CALENDAR_EVENT_SCHEMA(dataclasses.asdict(self, dict_factory=skip_none))
        except vol.Invalid as err:
            raise HomeAssistantError(
                f"Failed to validate CalendarEvent: {err}"
            ) from err

        # It is common to set a start an end date to be the same thing for
        # an all day event, but that is not a valid duration. Fix to have a
        # duration of one day.
        if (
            not isinstance(self.start, datetime.datetime)
            and not isinstance(self.end, datetime.datetime)
            and self.start == self.end
        ):
            self.end = self.start + datetime.timedelta(days=1)


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
            result[name] = {"dateTime": dt_util.as_local(value).isoformat()}
        elif isinstance(value, datetime.date):
            result[name] = {"date": value.isoformat()}
        else:
            result[name] = value
    return result


def _list_events_dict_factory(
    obj: Iterable[tuple[str, Any]]
) -> dict[str, JsonValueType]:
    """Convert CalendarEvent dataclass items to dictionary of attributes."""
    return {
        name: value
        for name, value in _event_dict_factory(obj).items()
        if name in LIST_EVENT_FIELDS and value is not None
    }


def _get_datetime_local(
    dt_or_d: datetime.datetime | datetime.date,
) -> datetime.datetime:
    """Convert a calendar event date/datetime to a datetime if needed."""
    if isinstance(dt_or_d, datetime.datetime):
        return dt_util.as_local(dt_or_d)
    return dt_util.start_of_local_day(dt_or_d)


def _get_api_date(dt_or_d: datetime.datetime | datetime.date) -> dict[str, str]:
    """Convert a calendar event date/datetime to a datetime if needed."""
    if isinstance(dt_or_d, datetime.datetime):
        return {"dateTime": dt_util.as_local(dt_or_d).isoformat()}
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
            if time[0] in ("+", "-"):
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
    return start + offset_time <= dt_util.now(start.tzinfo)


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

        now = dt_util.now()

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

    async def async_create_event(self, **kwargs: Any) -> None:
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

    async def async_update_event(
        self,
        uid: str,
        event: dict[str, Any],
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
            start_date = dt_util.parse_datetime(start)
            end_date = dt_util.parse_datetime(end)
        except (ValueError, AttributeError):
            return web.Response(status=HTTPStatus.BAD_REQUEST)
        if start_date is None or end_date is None:
            return web.Response(status=HTTPStatus.BAD_REQUEST)
        if start_date > end_date:
            return web.Response(status=HTTPStatus.BAD_REQUEST)

        try:
            calendar_event_list = await entity.async_get_events(
                request.app["hass"],
                dt_util.as_local(start_date),
                dt_util.as_local(end_date),
            )
        except HomeAssistantError as err:
            _LOGGER.debug("Error reading events: %s", err)
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


@websocket_api.websocket_command(
    {
        vol.Required("type"): "calendar/event/create",
        vol.Required("entity_id"): cv.entity_id,
        CONF_EVENT: WEBSOCKET_EVENT_SCHEMA,
    }
)
@websocket_api.async_response
async def handle_calendar_event_create(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle creation of a calendar event."""
    component: EntityComponent[CalendarEntity] = hass.data[DOMAIN]
    if not (entity := component.get_entity(msg["entity_id"])):
        connection.send_error(msg["id"], ERR_NOT_FOUND, "Entity not found")
        return

    if (
        not entity.supported_features
        or not entity.supported_features & CalendarEntityFeature.CREATE_EVENT
    ):
        connection.send_message(
            websocket_api.error_message(
                msg["id"], ERR_NOT_SUPPORTED, "Calendar does not support event creation"
            )
        )
        return

    try:
        await entity.async_create_event(**msg[CONF_EVENT])
    except HomeAssistantError as ex:
        connection.send_error(msg["id"], "failed", str(ex))
    else:
        connection.send_result(msg["id"])


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

    component: EntityComponent[CalendarEntity] = hass.data[DOMAIN]
    if not (entity := component.get_entity(msg["entity_id"])):
        connection.send_error(msg["id"], ERR_NOT_FOUND, "Entity not found")
        return

    if (
        not entity.supported_features
        or not entity.supported_features & CalendarEntityFeature.DELETE_EVENT
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


@websocket_api.websocket_command(
    {
        vol.Required("type"): "calendar/event/update",
        vol.Required("entity_id"): cv.entity_id,
        vol.Required(EVENT_UID): cv.string,
        vol.Optional(EVENT_RECURRENCE_ID): cv.string,
        vol.Optional(EVENT_RECURRENCE_RANGE): cv.string,
        vol.Required(CONF_EVENT): WEBSOCKET_EVENT_SCHEMA,
    }
)
@websocket_api.async_response
async def handle_calendar_event_update(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle creation of a calendar event."""
    component: EntityComponent[CalendarEntity] = hass.data[DOMAIN]
    if not (entity := component.get_entity(msg["entity_id"])):
        connection.send_error(msg["id"], ERR_NOT_FOUND, "Entity not found")
        return

    if (
        not entity.supported_features
        or not entity.supported_features & CalendarEntityFeature.UPDATE_EVENT
    ):
        connection.send_message(
            websocket_api.error_message(
                msg["id"], ERR_NOT_SUPPORTED, "Calendar does not support event update"
            )
        )
        return

    try:
        await entity.async_update_event(
            msg[EVENT_UID],
            msg[CONF_EVENT],
            recurrence_id=msg.get(EVENT_RECURRENCE_ID),
            recurrence_range=msg.get(EVENT_RECURRENCE_RANGE),
        )
    except (HomeAssistantError, ValueError) as ex:
        _LOGGER.error("Error handling Calendar Event call: %s", ex)
        connection.send_error(msg["id"], "failed", str(ex))
    else:
        connection.send_result(msg["id"])


def _validate_timespan(
    values: dict[str, Any]
) -> tuple[datetime.datetime | datetime.date, datetime.datetime | datetime.date]:
    """Parse a create event service call and convert the args ofr a create event entity call.

    This converts the input service arguments into a `start` and `end` date or date time. This
    exists because service calls use `start_date` and `start_date_time` whereas the
    normal entity methods can take either a `datetim` or `date` as a single `start` argument.
    It also handles the other service call variations like "in days" as well.
    """

    if event_in := values.get(EVENT_IN):
        days = event_in.get(EVENT_IN_DAYS, 7 * event_in.get(EVENT_IN_WEEKS, 0))
        today = datetime.date.today()
        return (
            today + datetime.timedelta(days=days),
            today + datetime.timedelta(days=days + 1),
        )

    if EVENT_START_DATE in values and EVENT_END_DATE in values:
        return (values[EVENT_START_DATE], values[EVENT_END_DATE])

    if EVENT_START_DATETIME in values and EVENT_END_DATETIME in values:
        return (values[EVENT_START_DATETIME], values[EVENT_END_DATETIME])

    raise ValueError("Missing required fields to set start or end date/datetime")


async def async_create_event(entity: CalendarEntity, call: ServiceCall) -> None:
    """Add a new event to calendar."""
    # Convert parameters to format used by async_create_event
    (start, end) = _validate_timespan(call.data)
    params = {
        **{k: v for k, v in call.data.items() if k not in EVENT_TIME_FIELDS},
        EVENT_START: start,
        EVENT_END: end,
    }
    await entity.async_create_event(**params)


async def async_list_events_service(
    calendar: CalendarEntity, service_call: ServiceCall
) -> ServiceResponse:
    """List events on a calendar during a time drange."""
    start = service_call.data.get(EVENT_START_DATETIME, dt_util.now())
    if EVENT_DURATION in service_call.data:
        end = start + service_call.data[EVENT_DURATION]
    else:
        end = service_call.data[EVENT_END_DATETIME]
    calendar_event_list = await calendar.async_get_events(
        calendar.hass, dt_util.as_local(start), dt_util.as_local(end)
    )
    return {
        "events": [
            dataclasses.asdict(event, dict_factory=_list_events_dict_factory)
            for event in calendar_event_list
        ]
    }
