"""CalDAV todo platform."""

import asyncio
from datetime import date, datetime, timedelta
from functools import partial
import logging
from typing import Any, cast, override

from caldav.calendarobjectresource import CalendarObjectResource, Todo
from caldav.collection import Calendar, SynchronizableCalendarObjectCollection
from caldav.lib.error import DAVError, NotFoundError
from caldav.lib.http_sync import requests as caldav_requests

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import CalDavConfigEntry
from .api import async_get_calendars, get_attr_value

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=15)
# A restored server may report no changes for a sync token it never issued
MAX_SKIPPED_UPDATES = 3

SUPPORTED_COMPONENT = "VTODO"
TODO_STATUS_MAP = {
    "NEEDS-ACTION": TodoItemStatus.NEEDS_ACTION,
    "IN-PROCESS": TodoItemStatus.NEEDS_ACTION,
    "COMPLETED": TodoItemStatus.COMPLETED,
    "CANCELLED": TodoItemStatus.COMPLETED,
}
TODO_STATUS_MAP_INV: dict[TodoItemStatus, str] = {
    TodoItemStatus.NEEDS_ACTION: "NEEDS-ACTION",
    TodoItemStatus.COMPLETED: "COMPLETED",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CalDavConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the CalDav todo platform for a config entry."""
    calendars = await async_get_calendars(hass, entry.runtime_data, SUPPORTED_COMPONENT)
    async_add_entities(
        (
            WebDavTodoListEntity(
                calendar,
                calendar_name,
                entry.entry_id,
            )
            for calendar, calendar_name in calendars
        ),
        True,
    )


def _get_changes(calendar: Calendar, sync_token: str | None) -> tuple[bool, str | None]:
    """Return whether a calendar changed since the sync token, and the new token.

    A failed sync-collection report (RFC 6578) counts as changed.
    """
    try:
        changes = cast(
            SynchronizableCalendarObjectCollection,
            calendar.get_objects_by_sync_token(sync_token, disable_fallback=True),
        )
    except (caldav_requests.exceptions.RequestException, DAVError) as err:
        _LOGGER.debug("Cannot read the changes, reading all items: %s", err)
        return True, None
    # A token with second precision can stay the same, but the change is listed
    changed = sync_token is None or changes.sync_token != sync_token or len(changes) > 0
    return changed, changes.sync_token


def _get_todo_items(calendar: Calendar) -> list[TodoItem]:
    """Fetch and parse todo items."""
    results = cast(
        list[CalendarObjectResource],
        calendar.search(todo=True, include_completed=True),
    )
    return [
        todo_item
        for resource in results
        if (todo_item := _todo_item(resource)) is not None
    ]


def _todo_item(resource: CalendarObjectResource) -> TodoItem | None:
    """Convert a caldav Todo into a TodoItem."""
    if (
        not hasattr(resource.vobject_instance, "vtodo")
        or not (todo := resource.vobject_instance.vtodo)
        or (uid := get_attr_value(todo, "uid")) is None
        or (summary := get_attr_value(todo, "summary")) is None
    ):
        return None
    due: date | datetime | None = None
    if due_value := get_attr_value(todo, "due"):
        if isinstance(due_value, datetime):
            due = dt_util.as_local(due_value)
        elif isinstance(due_value, date):
            due = due_value
    status = TODO_STATUS_MAP.get(
        get_attr_value(todo, "status") or "",
        TodoItemStatus.NEEDS_ACTION,
    )
    completed: datetime | None = None
    if status == TodoItemStatus.COMPLETED and isinstance(
        completed_value := get_attr_value(todo, "completed"), datetime
    ):
        completed = dt_util.as_local(completed_value)
    return TodoItem(
        uid=uid,
        summary=summary,
        status=status,
        due=due,
        description=get_attr_value(todo, "description"),
        completed=completed,
    )


class WebDavTodoListEntity(TodoListEntity):
    """CalDAV To-do list entity."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.SET_DUE_DATE_ON_ITEM
        | TodoListEntityFeature.SET_DUE_DATETIME_ON_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(
        self, calendar: Calendar, calendar_name: str | None, config_entry_id: str
    ) -> None:
        """Initialize WebDavTodoListEntity."""
        self._calendar = calendar
        self._attr_name = (calendar_name or "Unknown").capitalize()
        self._attr_unique_id = f"{config_entry_id}-{calendar.id}"
        self._sync_token: str | None = None
        self._skips_left = 0
        self._writes = 0
        self._writes_seen = 0

    async def async_update(self) -> None:
        """Update To-do list entity state."""
        changed, sync_token = await self.hass.async_add_executor_job(
            _get_changes, self._calendar, self._sync_token
        )
        writes = self._writes
        if not changed and self._skips_left and writes == self._writes_seen:
            self._skips_left -= 1
            return
        todo_items = await self.hass.async_add_executor_job(
            _get_todo_items, self._calendar
        )
        if not changed and todo_items != self._attr_todo_items:
            # The report missed a change
            sync_token = None
        self._attr_todo_items = todo_items
        self._sync_token = sync_token
        self._skips_left = MAX_SKIPPED_UPDATES
        self._writes_seen = writes

    @override
    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an item to the To-do list."""
        item_data: dict[str, Any] = {}
        if summary := item.summary:
            item_data["summary"] = summary
        if status := item.status:
            item_data["status"] = TODO_STATUS_MAP_INV.get(status, "NEEDS-ACTION")
        if due := item.due:
            item_data["due"] = due
        if description := item.description:
            item_data["description"] = description
        try:
            await self.hass.async_add_executor_job(
                partial(self._calendar.add_todo, **item_data),
            )
            self._writes += 1
            # refreshing async otherwise it would take too much time
            self.hass.async_create_task(self.async_update_ha_state(force_refresh=True))
        except (
            caldav_requests.exceptions.ConnectionError,
            caldav_requests.exceptions.Timeout,
            DAVError,
        ) as err:
            raise HomeAssistantError(f"CalDAV save error: {err}") from err

    @override
    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update a To-do item."""
        uid: str = cast(str, item.uid)
        try:
            todo = cast(
                Todo,
                await self.hass.async_add_executor_job(
                    self._calendar.get_todo_by_uid, uid
                ),
            )
        except NotFoundError as err:
            raise HomeAssistantError(f"Could not find To-do item {uid}") from err
        except (
            caldav_requests.exceptions.ConnectionError,
            caldav_requests.exceptions.Timeout,
            DAVError,
        ) as err:
            raise HomeAssistantError(f"CalDAV lookup error: {err}") from err
        vtodo = todo.icalendar_component
        vtodo["SUMMARY"] = item.summary or ""
        if status := item.status:
            previous = TODO_STATUS_MAP.get(
                vtodo.get("STATUS", ""), TodoItemStatus.NEEDS_ACTION
            )
            vtodo["STATUS"] = TODO_STATUS_MAP_INV.get(status, "NEEDS-ACTION")
            if status != TodoItemStatus.COMPLETED:
                vtodo.pop("COMPLETED", None)
            elif previous != TodoItemStatus.COMPLETED:
                vtodo.pop("COMPLETED", None)
                vtodo.add("COMPLETED", dt_util.utcnow())
        if due := item.due:
            todo.set_due(due)
        else:
            vtodo.pop("DUE", None)
        if description := item.description:
            vtodo["DESCRIPTION"] = description
        else:
            vtodo.pop("DESCRIPTION", None)
        try:
            await self.hass.async_add_executor_job(
                partial(
                    todo.save,
                    no_create=True,
                    obj_type="todo",
                ),
            )
            self._writes += 1
            # refreshing async otherwise it would take too much time
            self.hass.async_create_task(self.async_update_ha_state(force_refresh=True))
        except (
            caldav_requests.exceptions.ConnectionError,
            caldav_requests.exceptions.Timeout,
            DAVError,
        ) as err:
            raise HomeAssistantError(f"CalDAV save error: {err}") from err

    @override
    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete To-do items."""
        tasks = (
            self.hass.async_add_executor_job(self._calendar.get_todo_by_uid, uid)
            for uid in uids
        )

        try:
            items = cast(list[Todo], await asyncio.gather(*tasks))
        except NotFoundError as err:
            raise HomeAssistantError("Could not find To-do item") from err
        except (
            caldav_requests.exceptions.ConnectionError,
            caldav_requests.exceptions.Timeout,
            DAVError,
        ) as err:
            raise HomeAssistantError(f"CalDAV lookup error: {err}") from err

        # Run serially as some CalDAV servers do not support concurrent modifications
        for item in items:
            try:
                await self.hass.async_add_executor_job(item.delete)
            except (
                caldav_requests.exceptions.ConnectionError,
                caldav_requests.exceptions.Timeout,
                DAVError,
            ) as err:
                raise HomeAssistantError(f"CalDAV delete error: {err}") from err
            self._writes += 1
        # refreshing async otherwise it would take too much time
        self.hass.async_create_task(self.async_update_ha_state(force_refresh=True))
