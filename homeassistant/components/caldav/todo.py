"""CalDAV todo platform."""
from __future__ import annotations

from datetime import timedelta
from functools import partial
import logging

import caldav

from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import async_get_calendars, get_attr_value
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=15)

SUPPORTED_COMPONENT = "VTODO"
TODO_STATUS_MAP = {
    "NEEDS-ACTION": TodoItemStatus.NEEDS_ACTION,
    "IN-PROCESS": TodoItemStatus.NEEDS_ACTION,
    "COMPLETED": TodoItemStatus.COMPLETED,
    "CANCELLED": TodoItemStatus.COMPLETED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the CalDav todo platform for a config entry."""
    client: caldav.DAVClient = hass.data[DOMAIN][entry.entry_id]
    calendars = await async_get_calendars(hass, client, SUPPORTED_COMPONENT)
    async_add_entities(
        (
            WebDavTodoListEntity(
                calendar,
                entry.entry_id,
            )
            for calendar in calendars
        ),
        True,
    )


def _todo_item(resource: caldav.CalendarObjectResource) -> TodoItem | None:
    """Convert a caldav Todo into a TodoItem."""
    if (
        not hasattr(resource.instance, "vtodo")
        or not (todo := resource.instance.vtodo)
        or (uid := get_attr_value(todo, "uid")) is None
        or (summary := get_attr_value(todo, "summary")) is None
    ):
        return None
    return TodoItem(
        uid=uid,
        summary=summary,
        status=TODO_STATUS_MAP.get(
            get_attr_value(todo, "status") or "",
            TodoItemStatus.NEEDS_ACTION,
        ),
    )


class WebDavTodoListEntity(TodoListEntity):
    """CalDAV To-do list entity."""

    _attr_has_entity_name = True

    def __init__(self, calendar: caldav.Calendar, config_entry_id: str) -> None:
        """Initialize WebDavTodoListEntity."""
        self._calendar = calendar
        self._attr_name = (calendar.name or "Unknown").capitalize()
        self._attr_unique_id = f"{config_entry_id}-{calendar.id}"

    async def async_update(self) -> None:
        """Update To-do list entity state."""
        results = await self.hass.async_add_executor_job(
            partial(
                self._calendar.search,
                todo=True,
                include_completed=True,
            )
        )
        self._attr_todo_items = [
            todo_item
            for resource in results
            if (todo_item := _todo_item(resource)) is not None
        ]
