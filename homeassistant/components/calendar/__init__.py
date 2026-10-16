"""Support for Calendar event device sensors."""

import dataclasses
import datetime as dt
from http import HTTPStatus
import logging
import re
from typing import Any, cast

from aiohttp import web
import probatio

from homeassistant.auth.models import User
from homeassistant.auth.permissions.const import POLICY_CONTROL, POLICY_READ
from homeassistant.components import frontend, http, websocket_api
from homeassistant.components.http import KEY_HASS_USER
from homeassistant.components.websocket_api import (
    ERR_INVALID_FORMAT,
    ERR_NOT_FOUND,
    ERR_NOT_SUPPORTED,
    ActiveConnection,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EVENT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonValueType

from .const import (
    CREATE_EVENT_SERVICE,
    DATA_COMPONENT,
    DOMAIN,
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
    SERVICE_GET_EVENTS,
    CalendarEntityFeature,
    CalendarEntityStateAttribute,
    CalendarEventStatus,
)
from .entity import CalendarEntity, CalendarEntityDescription, CalendarEvent
from .helper import (
    MIN_NEW_EVENT_DURATION,
    api_event_dict_factory,
    as_local_timezone,
    empty_as_none,
    has_consistent_timezone,
    has_min_duration,
    has_same_type,
    validate_rrule,
)
from .services import CREATE_EVENT_SCHEMA, async_setup_services

# mypy: disallow-any-generics

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = dt.timedelta(seconds=60)


WEBSOCKET_EVENT_SCHEMA = probatio.Schema(
    probatio.All(
        {
            probatio.Required(EVENT_START): probatio.Any(cv.date, cv.datetime),
            probatio.Required(EVENT_END): probatio.Any(cv.date, cv.datetime),
            probatio.Required(EVENT_SUMMARY): cv.string,
            probatio.Optional(EVENT_DESCRIPTION): cv.string,
            probatio.Optional(EVENT_LOCATION): cv.string,
            probatio.Optional(EVENT_RRULE): validate_rrule,
        },
        has_same_type(EVENT_START, EVENT_END),
        has_consistent_timezone(EVENT_START, EVENT_END),
        as_local_timezone(EVENT_START, EVENT_END),
        has_min_duration(EVENT_START, EVENT_END, MIN_NEW_EVENT_DURATION),
    )
)


__all__ = [
    "CREATE_EVENT_SCHEMA",
    "CREATE_EVENT_SERVICE",
    "DOMAIN",
    "ENTITY_ID_FORMAT",
    "EVENT_DESCRIPTION",
    "EVENT_DURATION",
    "EVENT_END",
    "EVENT_END_DATE",
    "EVENT_END_DATETIME",
    "EVENT_IN",
    "EVENT_IN_DAYS",
    "EVENT_IN_WEEKS",
    "EVENT_LOCATION",
    "EVENT_RECURRENCE_ID",
    "EVENT_RECURRENCE_RANGE",
    "EVENT_RRULE",
    "EVENT_START",
    "EVENT_START_DATE",
    "EVENT_START_DATETIME",
    "EVENT_SUMMARY",
    "EVENT_TIME_FIELDS",
    "EVENT_TYPES",
    "EVENT_UID",
    "LIST_EVENT_FIELDS",
    "PLATFORM_SCHEMA",
    "PLATFORM_SCHEMA_BASE",
    "SERVICE_GET_EVENTS",
    "WEBSOCKET_EVENT_SCHEMA",
    "CalendarEntity",
    "CalendarEntityDescription",
    "CalendarEntityFeature",
    "CalendarEntityStateAttribute",
    "CalendarEvent",
    "CalendarEventStatus",
    "extract_offset",
    "is_offset_reached",
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track states and offer events for calendars."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[CalendarEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    hass.http.register_view(CalendarListView(component))
    hass.http.register_view(CalendarEventView(component))

    frontend.async_register_built_in_panel(hass, "calendar", "calendar", "mdi:calendar")

    websocket_api.async_register_command(hass, handle_calendar_event_create)
    websocket_api.async_register_command(hass, handle_calendar_event_delete)
    websocket_api.async_register_command(hass, handle_calendar_event_update)
    websocket_api.async_register_command(hass, handle_calendar_event_subscribe)

    async_setup_services(hass)
    await component.async_setup(config)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


def get_date(date: dict[str, Any]) -> dt.datetime:
    """Get the dateTime from date or dateTime as a local."""
    if "date" in date:
        parsed_date = dt_util.parse_date(date["date"])
        assert parsed_date
        return dt_util.start_of_local_day(dt.datetime.combine(parsed_date, dt.time.min))
    parsed_datetime = dt_util.parse_datetime(date["dateTime"])
    assert parsed_datetime
    return dt_util.as_local(parsed_datetime)


def extract_offset(summary: str, offset_prefix: str) -> tuple[str, dt.timedelta]:
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

        offset_time = cv.time_period_str(time)
        summary = (summary[: search.start()] + summary[search.end() :]).strip()
        return (summary, offset_time)
    return (summary, dt.timedelta())


def is_offset_reached(start: dt.datetime, offset_time: dt.timedelta) -> bool:
    """Have we reached the offset time specified in the event title."""
    if offset_time == dt.timedelta():
        return False
    return start + offset_time <= dt_util.now(start.tzinfo)


class CalendarEventView(http.HomeAssistantView):
    """View to retrieve calendar content."""

    url = "/api/calendars/{entity_id}"
    name = "api:calendars:calendar"

    def __init__(self, component: EntityComponent[CalendarEntity]) -> None:
        """Initialize calendar view."""
        self.component = component

    async def get(self, request: web.Request, entity_id: str) -> web.Response:
        """Return calendar events."""
        user: User = request[KEY_HASS_USER]
        if not user.permissions.check_entity(entity_id, POLICY_READ):
            raise Unauthorized(entity_id=entity_id)

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
        except ValueError, AttributeError:
            return web.Response(status=HTTPStatus.BAD_REQUEST)
        if start_date is None or end_date is None:
            return web.Response(status=HTTPStatus.BAD_REQUEST)
        if start_date > end_date:
            return web.Response(status=HTTPStatus.BAD_REQUEST)

        try:
            calendar_event_list = await entity.async_get_events(
                request.app[http.KEY_HASS],
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
                dataclasses.asdict(event, dict_factory=api_event_dict_factory)
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
        user: User = request[KEY_HASS_USER]
        hass = request.app[http.KEY_HASS]
        entity_perm = user.permissions.check_entity
        calendar_list: list[dict[str, str]] = []

        for entity in self.component.entities:
            if not entity_perm(entity.entity_id, POLICY_READ):
                continue
            state = hass.states.get(entity.entity_id)
            assert state
            calendar_list.append({"name": state.name, "entity_id": entity.entity_id})

        return self.json(sorted(calendar_list, key=lambda x: cast(str, x["name"])))


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "calendar/event/create",
        probatio.Required("entity_id"): cv.entity_id,
        CONF_EVENT: WEBSOCKET_EVENT_SCHEMA,
    }
)
@websocket_api.async_response
async def handle_calendar_event_create(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle creation of a calendar event."""
    if not connection.user.permissions.check_entity(msg["entity_id"], POLICY_CONTROL):
        raise Unauthorized(entity_id=msg["entity_id"])

    if not (entity := hass.data[DATA_COMPONENT].get_entity(msg["entity_id"])):
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
        probatio.Required("type"): "calendar/event/delete",
        probatio.Required("entity_id"): cv.entity_id,
        probatio.Required(EVENT_UID): cv.string,
        probatio.Optional(EVENT_RECURRENCE_ID): probatio.Any(
            probatio.All(cv.string, empty_as_none), None
        ),
        probatio.Optional(EVENT_RECURRENCE_RANGE): cv.string,
    }
)
@websocket_api.async_response
async def handle_calendar_event_delete(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle delete of a calendar event."""
    if not connection.user.permissions.check_entity(msg["entity_id"], POLICY_CONTROL):
        raise Unauthorized(entity_id=msg["entity_id"])

    if not (entity := hass.data[DATA_COMPONENT].get_entity(msg["entity_id"])):
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
        probatio.Required("type"): "calendar/event/update",
        probatio.Required("entity_id"): cv.entity_id,
        probatio.Required(EVENT_UID): cv.string,
        probatio.Optional(EVENT_RECURRENCE_ID): probatio.Any(
            probatio.All(cv.string, empty_as_none), None
        ),
        probatio.Optional(EVENT_RECURRENCE_RANGE): cv.string,
        probatio.Required(CONF_EVENT): WEBSOCKET_EVENT_SCHEMA,
    }
)
@websocket_api.async_response
async def handle_calendar_event_update(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle update of a calendar event."""
    if not connection.user.permissions.check_entity(msg["entity_id"], POLICY_CONTROL):
        raise Unauthorized(entity_id=msg["entity_id"])

    if not (entity := hass.data[DATA_COMPONENT].get_entity(msg["entity_id"])):
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


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "calendar/event/subscribe",
        probatio.Required("entity_id"): cv.entity_domain(DOMAIN),
        probatio.Required("start"): cv.datetime,
        probatio.Required("end"): cv.datetime,
    }
)
@websocket_api.async_response
async def handle_calendar_event_subscribe(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Subscribe to calendar event updates."""
    entity_id: str = msg["entity_id"]

    if not connection.user.permissions.check_entity(entity_id, POLICY_READ):
        raise Unauthorized(entity_id=entity_id)

    if not (entity := hass.data[DATA_COMPONENT].get_entity(entity_id)):
        connection.send_error(
            msg["id"],
            ERR_NOT_FOUND,
            f"Calendar entity not found: {entity_id}",
        )
        return

    start_date = dt_util.as_local(msg["start"])
    end_date = dt_util.as_local(msg["end"])

    if start_date >= end_date:
        connection.send_error(
            msg["id"],
            ERR_INVALID_FORMAT,
            "Start must be before end",
        )
        return

    subscription_id = msg["id"]

    @callback
    def event_listener(events: list[JsonValueType] | None) -> None:
        """Push updated calendar events to websocket."""
        if subscription_id not in connection.subscriptions:
            return
        connection.send_message(
            websocket_api.event_message(
                subscription_id,
                {
                    "events": events,
                },
            )
        )

    connection.subscriptions[subscription_id] = entity.async_subscribe_events(
        start_date, end_date, event_listener
    )
    connection.send_result(subscription_id)

    # Push initial events only to the new subscriber
    entity.async_update_single_event_listener(start_date, end_date, event_listener)
