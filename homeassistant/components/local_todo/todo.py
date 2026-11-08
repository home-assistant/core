"""A Local To-do todo platform."""

import asyncio
from collections.abc import Iterable, Mapping
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.setup import SetupPhases, async_pause_setup
from homeassistant.util import dt as dt_util

from . import LocalTodoConfigEntry
from .const import CONF_CATEGORIES, CONF_TODO_LIST_NAME, DOMAIN
from .store import (
    LocalTodoListStore,
    change_categories,
    item_categories,
    parse_calendar,
)

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

    # Lists saved before categories were declared may have undeclared ones
    _async_declare_categories(hass, config_entry, item_categories(calendar))
    entity = LocalTodoListEntity(config_entry, calendar, name)
    async_add_entities([entity], True)

    if migrated:
        await entity.async_save()


@callback
def _async_declare_categories(
    hass: HomeAssistant,
    config_entry: LocalTodoConfigEntry,
    categories: Iterable[str | None],
) -> list[str] | None:
    """Add the categories that aren't declared yet to the options.

    Return the declared categories when they changed.
    """
    declared = list(config_entry.options.get(CONF_CATEGORIES, []))
    new = [
        category
        for category in dict.fromkeys(categories)
        if category and category not in declared
    ]
    if not new:
        return None
    declared += new
    hass.config_entries.async_update_entry(
        config_entry, options={**config_entry.options, CONF_CATEGORIES: declared}
    )
    return declared


def _convert_item(item: TodoItem) -> Todo:
    """Convert a HomeAssistant TodoItem to an ical Todo."""
    if item.category and "," in item.category:
        # ical splits CATEGORIES on commas when reading, even escaped ones
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_category",
            translation_placeholders={"category": item.category},
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
    todo.categories = [item.category] if item.category else []
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
        | TodoListEntityFeature.SET_CATEGORY_ON_ITEM
    )
    _attr_should_poll = False

    def __init__(
        self, config_entry: LocalTodoConfigEntry, calendar: Calendar, name: str
    ) -> None:
        """Initialize LocalTodoListEntity."""
        self._config_entry = config_entry
        self._data = config_entry.runtime_data
        self._store: LocalTodoListStore = self._data.store
        self._calendar = calendar
        self._calendar_lock = asyncio.Lock()
        self._attr_name = name
        self._attr_unique_id = config_entry.entry_id
        self._attr_todo_categories = (
            list(config_entry.options.get(CONF_CATEGORIES, [])) or None
        )

    @callback
    def _async_declare_category(self, category: str | None) -> None:
        """Declare the category of an item if it's new."""
        if declared := _async_declare_categories(
            self.hass, self._config_entry, [category]
        ):
            self._attr_todo_categories = declared

    @override
    async def async_added_to_hass(self) -> None:
        """Let the options flow change the categories of the loaded list."""
        self._data.entity = self

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Stop receiving category changes."""
        self._data.entity = None

    async def async_change_categories(
        self, categories: list[str], changes: Mapping[str, str | None]
    ) -> None:
        """Set the categories, renaming or clearing them on the items."""
        async with self._calendar_lock:
            previous = [todo.categories for todo in self._calendar.todos]
            if change_categories(self._calendar, changes):
                try:
                    await self.async_save()
                except HomeAssistantError:
                    # Keep the items consistent with the options, left unchanged
                    for todo, previous_categories in zip(
                        self._calendar.todos, previous, strict=True
                    ):
                        todo.categories = previous_categories
                    raise
        self._attr_todo_categories = categories or None
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
                    category=next(iter(item.categories), None),
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
            self._async_declare_category(item.category)
        await self.async_update_ha_state(force_refresh=True)

    @override
    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update an item in the To-do list."""
        todo = _convert_item(item)
        async with self._calendar_lock:
            todo_store = self._new_todo_store()
            await self.hass.async_add_executor_job(todo_store.edit, todo.uid, todo)
            await self.async_save()
            self._async_declare_category(item.category)
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
