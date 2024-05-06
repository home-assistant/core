"""A Local To-do todo platform."""

import logging

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
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_TODO_LIST_NAME, DOMAIN
from .store import LocalTodoListStore

_LOGGER = logging.getLogger(__name__)


PRODID = "-//homeassistant.io//local_todo 1.0//EN"

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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the local_todo todo platform."""

    store = hass.data[DOMAIN][config_entry.entry_id]
    ics = await store.async_load()
    calendar = IcsCalendarStream.calendar_from_ics(ics)
    calendar.prodid = PRODID

    name = config_entry.data[CONF_TODO_LIST_NAME]
    entity = LocalTodoListEntity(store, calendar, name, unique_id=config_entry.entry_id)
    async_add_entities([entity], True)


def _convert_item(item: TodoItem) -> Todo:
    """Convert a HomeAssistant TodoItem to an ical Todo."""
    todo = Todo()
    if item.uid:
        todo.uid = item.uid
    if item.summary:
        todo.summary = item.summary
    if item.status:
        todo.status = ICS_TODO_STATUS_MAP_INV[item.status]
    todo.due = item.due
    todo.description = item.description
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
    )
    _attr_should_poll = False

    def __init__(
        self,
        store: LocalTodoListStore,
        calendar: Calendar,
        name: str,
        unique_id: str,
    ) -> None:
        """Initialize LocalTodoListEntity."""
        self._store = store
        self._calendar = calendar
        self._attr_name = name.capitalize()
        self._attr_unique_id = unique_id

    async def async_update(self) -> None:
        """Update entity state based on the local To-do items."""
        self._attr_todo_items = [
            TodoItem(
                uid=item.uid,
                summary=item.summary or "",
                status=ICS_TODO_STATUS_MAP.get(
                    item.status or TodoStatus.NEEDS_ACTION, TodoItemStatus.NEEDS_ACTION
                ),
                due=item.due,
                description=item.description,
            )
            for item in self._calendar.todos
        ]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an item to the To-do list."""
        todo = _convert_item(item)
        TodoStore(self._calendar).add(todo)
        await self._async_save()
        await self.async_update_ha_state(force_refresh=True)

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update an item to the To-do list."""
        todo = _convert_item(item)
        TodoStore(self._calendar).edit(todo.uid, todo)
        await self._async_save()
        await self.async_update_ha_state(force_refresh=True)

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete an item from the To-do list."""
        store = TodoStore(self._calendar)
        for uid in uids:
            store.delete(uid)
        await self._async_save()
        await self.async_update_ha_state(force_refresh=True)

    async def async_move_todo_item(
        self, uid: str, previous_uid: str | None = None
    ) -> None:
        """Re-order an item to the To-do list."""
        if uid == previous_uid:
            return
        todos = self._calendar.todos
        item_idx: dict[str, int] = {itm.uid: idx for idx, itm in enumerate(todos)}
        if uid not in item_idx:
            raise HomeAssistantError(
                "Item '{uid}' not found in todo list {self.entity_id}"
            )
        if previous_uid and previous_uid not in item_idx:
            raise HomeAssistantError(
                "Item '{previous_uid}' not found in todo list {self.entity_id}"
            )
        dst_idx = item_idx[previous_uid] + 1 if previous_uid else 0
        src_idx = item_idx[uid]
        src_item = todos.pop(src_idx)
        if dst_idx > src_idx:
            dst_idx -= 1
        todos.insert(dst_idx, src_item)
        await self._async_save()
        await self.async_update_ha_state(force_refresh=True)

    async def _async_save(self) -> None:
        """Persist the todo list to disk."""
        content = IcsCalendarStream.calendar_to_ics(self._calendar)
        await self._store.async_store(content)
