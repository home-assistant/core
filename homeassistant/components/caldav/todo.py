"""CalDAV todo platform."""
from __future__ import annotations

from functools import partial
import logging

import caldav

from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import get_attr_value

_LOGGER = logging.getLogger(__name__)

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
    calendars = await hass.async_add_executor_job(client.principal().calendars)
    entities = []
    for calendar in calendars:
        supported_components = await hass.async_add_executor_job(
            calendar.get_supported_components
        )
        if "VTODO" not in supported_components:
            continue
        entities.append(
            WebDavTodoListEntity(
                calendar,
                entry.entry_id,
            )
        )
    async_add_entities(entities, True)


class WebDavTodoListEntity(TodoListEntity):
    """CalDAV To-do list entity."""

    _attr_has_entity_name = True

    def __init__(self, calendar: caldav.Calendar, config_entry_id: str) -> None:
        """Initialize WebDavTodoListEntity."""
        self._calendar = calendar
        self._attr_name = (calendar.name or "Unknown").capitalize()
        self._attr_unique_id = f"{config_entry_id}-{calendar.id}"
        self._attr_should_poll = True

    async def async_update(self) -> None:
        """Update To-do list entity state."""
        results = await self.hass.async_add_executor_job(
            partial(
                self._calendar.search,
                todo=True,
                include_completed=True,
            )
        )
        todos = [
            item.instance.vtodo for item in results if hasattr(item.instance, "vtodo")
        ]
        self._attr_todo_items = [
            TodoItem(
                summary=get_attr_value(todo, "summary") or "",
                status=TODO_STATUS_MAP.get(
                    get_attr_value(todo, "status") or "",
                    TodoItemStatus.NEEDS_ACTION,
                ),
            )
            for todo in todos
        ]
