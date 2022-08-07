"""The Local Calendar integration."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify

from .calendar import LocalCalendarEntity
from .const import CONF_CALENDAR_NAME, DOMAIN
from .store import LocalCalendarStore

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [Platform.CALENDAR]

STORAGE_PATH = ".storage/local_calendar.{key}.ics"

CONF_EVENT = "event"
CONF_UID = "uid"
CONF_RECURRENCE_ID = "recurrence_id"
CONF_RECURRENCE_RANGE = "recurrence_range"
CONF_START = "dtstart"
CONF_END = "dtend"
CONF_SUMMARY = "summary"
CONF_DESCRIPTION = "description"
CONF_LOCATION = "location"
CONF_RRULE = "rrule"


CALENDAR_EVENT_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_UID): cv.string,
        vol.Optional(CONF_RECURRENCE_ID): cv.string,
        vol.Optional(CONF_START): vol.Any(cv.datetime, cv.date),
        vol.Optional(CONF_END): vol.Any(cv.datetime, cv.date),
        vol.Optional(CONF_SUMMARY): cv.string,
        vol.Optional(CONF_DESCRIPTION): cv.string,
        vol.Optional(CONF_LOCATION): cv.string,
        vol.Optional(CONF_RRULE): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Local Calendar."""

    websocket_api.async_register_command(hass, handle_calendar_event_create)
    websocket_api.async_register_command(hass, handle_calendar_event_update)
    websocket_api.async_register_command(hass, handle_calendar_event_delete)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Local Calendar from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    key = slugify(entry.data[CONF_CALENDAR_NAME])
    path = Path(hass.config.path(STORAGE_PATH.format(key=key)))
    hass.data[DOMAIN][entry.entry_id] = LocalCalendarStore(hass, path)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def _get_calendar_entity(hass: HomeAssistant, entity_id: str) -> LocalCalendarEntity:
    if (component := hass.data.get("calendar")) is None:
        raise HomeAssistantError("Calendar integration not set up")

    if (entity := component.get_entity(entity_id)) is None or not isinstance(
        entity, LocalCalendarEntity
    ):
        raise HomeAssistantError(f"Calendar entity not found: {entity_id}")
    return entity


@websocket_api.websocket_command(
    {
        vol.Required("type"): "calendar/event/create",
        vol.Required("entity_id"): cv.entity_id,
        vol.Required(CONF_EVENT): CALENDAR_EVENT_SCHEMA,
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
    try:
        result = await entity.async_create_event(**msg[CONF_EVENT])
    except (HomeAssistantError, ValueError) as ex:
        connection.send_error(msg["id"], "failed", str(ex))
    else:
        connection.send_result(msg["id"], {CONF_UID: result.get(CONF_UID)})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "calendar/event/update",
        vol.Required("entity_id"): cv.entity_id,
        vol.Required(CONF_EVENT): CALENDAR_EVENT_SCHEMA,
        vol.Optional("recurrence_range"): cv.string,
    }
)
@websocket_api.async_response
async def handle_calendar_event_update(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle update of a calendar event."""
    try:
        entity = _get_calendar_entity(hass, msg["entity_id"])
    except HomeAssistantError as ex:
        connection.send_error(msg["id"], "failed", str(ex))
        return
    try:
        await entity.async_update_event(**msg[CONF_EVENT])
    except (HomeAssistantError, ValueError) as ex:
        _LOGGER.error("Error handling Calendar Event call: %s", ex)
        connection.send_error(msg["id"], "failed", str(ex))
    else:
        connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "calendar/event/delete",
        vol.Required("entity_id"): cv.entity_id,
        vol.Required(CONF_UID): cv.string,
        vol.Optional(CONF_RECURRENCE_ID): cv.string,
        vol.Optional("recurrence_range"): cv.string,
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

    try:
        await entity.async_delete_event(
            msg[CONF_UID],
            recurrence_id=msg.get(CONF_RECURRENCE_ID),
            recurrence_range=msg.get(CONF_RECURRENCE_RANGE),
        )
    except (HomeAssistantError, ValueError) as ex:
        _LOGGER.error("Error handling Calendar Event call: %s", ex)
        connection.send_error(msg["id"], "failed", str(ex))
    else:
        connection.send_result(msg["id"])
