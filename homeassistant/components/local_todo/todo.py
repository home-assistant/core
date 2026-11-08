"""A Local To-do todo platform."""

import asyncio
from collections.abc import Mapping
import datetime as dt
import logging
from typing import override

from ical.calendar import Calendar
from ical.calendar_stream import IcsCalendarStream
from ical.store import TodoStore
from ical.todo import Todo, TodoStatus

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.setup import SetupPhases, async_pause_setup
from homeassistant.util import dt as dt_util

from . import LocalTodoConfigEntry, LocalTodoData
from .const import CONF_SECTIONS, CONF_TODO_LIST_NAME, DOMAIN
from .store import LocalTodoListStore, change_sections, parse_calendar

_LOGGER = logging.getLogger(__name__)


PRODID = "-//homeassistant.io//local_todo 2.0//EN"
PRODID_REQUIRES_MIGRATION = "-//homeassistant.io//local_todo 1.0//EN"

ICS_TODO_STATUS_MAP = {
    TodoStatus.IN_PROCESS: TodoItemStatus.NEEDS_ACTION,
    TodoStatus.NEEDS_ACTION: TodoItemStatus.NEEDS_ACTION,
    TodoStatus.COMPLETED: TodoItemStatus.COMPLETED,
    TodoStatus.CANCELLED: TodoItemStatus.COMPLETED,
}
ICS_TODO_STATUS_MAP_INV = {
    TodoItemStatus.COMPLETED: TodoStatus.COMPLETED,
    TodoItemStatus.NEEDS_ACTION: TodoStatus.NEEDS_ACTION,
}


def _migrate_calendar(calendar: Calendar) -> bool:
    """Upgrade due dates to rfc5545 format.

    In rfc5545 due dates are exclusive, however we previously set the due date
    as inclusive based on what the user set in the UI. A task is considered
    overdue at midnight at the start of a date so we need to shift the due date
    to the next day for old calendar versions.
    """
    if calendar.prodid is None or calendar.prodid != PRODID_REQUIRES_MIGRATION:
        return False
    migrated = False
    for todo in calendar.todos:
        if todo.due is None or isinstance(todo.due, dt.datetime):
            continue
        todo.due += dt.timedelta(days=1)
        migrated = True
    return migrated


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LocalTodoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the local_todo todo platform."""

    name = config_entry.data[CONF_TODO_LIST_NAME]
    data = config_entry.runtime_data
    store = data.store
    ics = await store.async_load()

    with async_pause_setup(hass, SetupPhases.WAIT_IMPORT_PACKAGES):
        # calendar_from_ics will dynamically load packages
        # the first time it is called, so we need to do it
        # in a separate thread to avoid blocking the event loop
        calendar, repaired = await hass.async_add_import_executor_job(
            parse_calendar, ics
        )
    if repaired:
        _LOGGER.warning(
            "Repaired malformed iCalendar file for to-do list %s",
            name,
        )
    migrated = repaired

    if _migrate_calendar(calendar):
        migrated = True
    calendar.prodid = PRODID

    entity = LocalTodoListEntity(
        data,
        calendar,
        name,
        unique_id=config_entry.entry_id,
        sections=list(config_entry.options.get(CONF_SECTIONS, [])),
    )
    async_add_entities([entity], True)

    if migrated:
        await entity.async_save()


def _convert_item(item: TodoItem) -> Todo:
    """Convert a HomeAssistant TodoItem to an ical Todo."""
    if item.section and "," in item.section:
        # ical splits CATEGORIES on commas when reading, even escaped ones
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_section",
            translation_placeholders={"section": item.section},
        )
    todo = Todo()
    if item.uid:
        todo.uid = item.uid
    if item.summary:
        todo.summary = item.summary
    if item.status:
        todo.status = ICS_TODO_STATUS_MAP_INV[item.status]
    todo.due = item.due
    if todo.due and not isinstance(todo.due, dt.datetime):
        todo.due += dt.timedelta(days=1)
    todo.description = item.description
    todo.categories = [item.section] if item.section else []
    return todo


class LocalTodoListEntity(TodoListEntity):
    """A To-do List representation of the Shopping List."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.MOVE_TODO_ITEM
        | TodoListEntityFeature.SET_DUE_DATETIME_ON_ITEM
        | TodoListEntityFeature.SET_DUE_DATE_ON_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
        | TodoListEntityFeature.SET_SECTION_ON_ITEM
    )
    _attr_should_poll = False

    def __init__(
        self,
        data: LocalTodoData,
        calendar: Calendar,
        name: str,
        unique_id: str,
        sections: list[str],
    ) -> None:
        """Initialize LocalTodoListEntity."""
        self._data = data
        self._store: LocalTodoListStore = data.store
        self._calendar = calendar
        self._calendar_lock = asyncio.Lock()
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_todo_sections = sections or None

    @override
    async def async_added_to_hass(self) -> None:
        """Let the options flow change the sections of the loaded list."""
        self._data.entity = self

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Stop receiving section changes."""
        self._data.entity = None

    async def async_change_sections(
        self, sections: list[str], changes: Mapping[str, str | None]
    ) -> None:
        """Set the sections, renaming or clearing them on the items."""
        async with self._calendar_lock:
            previous = [todo.categories for todo in self._calendar.todos]
            if change_sections(self._calendar, changes):
                try:
                    await self.async_save()
                except HomeAssistantError:
                    # Keep the items consistent with the options, left unchanged
                    for todo, categories in zip(
                        self._calendar.todos, previous, strict=True
                    ):
                        todo.categories = categories
                    raise
        self._attr_todo_sections = sections or None
        await self.async_update_ha_state(force_refresh=True)

    def _new_todo_store(self) -> TodoStore:
        return TodoStore(self._calendar, tzinfo=dt_util.get_default_time_zone())

    async def async_update(self) -> None:
        """Update entity state based on the local To-do items."""
        todo_items = []
        for item in self._calendar.todos:
            if (due := item.due) and not isinstance(due, dt.datetime):
                due -= dt.timedelta(days=1)
            todo_items.append(
                TodoItem(
                    uid=item.uid,
                    summary=item.summary or "",
                    status=ICS_TODO_STATUS_MAP.get(
                        item.status or TodoStatus.NEEDS_ACTION,
                        TodoItemStatus.NEEDS_ACTION,
                    ),
                    due=due,
                    description=item.description,
                    completed=item.completed,
                    section=next(iter(item.categories), None),
                )
            )
        self._attr_todo_items = todo_items

    @override
    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an item to the To-do list."""
        todo = _convert_item(item)
        async with self._calendar_lock:
            todo_store = self._new_todo_store()
            await self.hass.async_add_executor_job(todo_store.add, todo)
            await self.async_save()
        await self.async_update_ha_state(force_refresh=True)

    @override
    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update an item in the To-do list."""
        todo = _convert_item(item)
        async with self._calendar_lock:
            todo_store = self._new_todo_store()
            await self.hass.async_add_executor_job(todo_store.edit, todo.uid, todo)
            await self.async_save()
        await self.async_update_ha_state(force_refresh=True)

    @override
    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete an item from the To-do list."""
        async with self._calendar_lock:
            todo_store = self._new_todo_store()
            for uid in uids:
                todo_store.delete(uid)
            await self.async_save()
        await self.async_update_ha_state(force_refresh=True)

    @override
    async def async_move_todo_item(
        self, uid: str, previous_uid: str | None = None
    ) -> None:
        """Re-order an item to the To-do list."""
        if uid == previous_uid:
            return
        async with self._calendar_lock:
            todos = self._calendar.todos
            item_idx: dict[str, int] = {itm.uid: idx for idx, itm in enumerate(todos)}
            if uid not in item_idx:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="item_not_found",
                    translation_placeholders={"uid": uid, "entity_id": self.entity_id},
                )
            if previous_uid and previous_uid not in item_idx:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="item_not_found",
                    translation_placeholders={
                        "uid": previous_uid,
                        "entity_id": self.entity_id,
                    },
                )
            dst_idx = item_idx[previous_uid] + 1 if previous_uid else 0
            src_idx = item_idx[uid]
            src_item = todos.pop(src_idx)
            if dst_idx > src_idx:
                dst_idx -= 1
            todos.insert(dst_idx, src_item)
            await self.async_save()
        await self.async_update_ha_state(force_refresh=True)

    async def async_save(self) -> None:
        """Persist the todo list to disk."""
        content = IcsCalendarStream.calendar_to_ics(self._calendar)
        await self._store.async_store(content)
