"""A local todo list todo platform."""

import dataclasses
import logging

from ical.calendar import Calendar
from ical.calendar_stream import IcsCalendarStream
from ical.store import TodoStore
from ical.todo import Todo, TodoStatus
from pydantic import ValidationError
import voluptuous as vol

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


class LocalTodoListEntity(TodoListEntity):
    """A To-do List representation of the Shopping List."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.MOVE_TODO_ITEM
    )

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
        self._compute_state()

    async def async_get_todo_items(self) -> list[TodoItem]:
        """Get items in the To-do list."""
        return self._todo_items

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an item to the To-do list."""
        try:
            todo = Todo.parse_obj(
                {k: v for k, v in dataclasses.asdict(item).items() if v is not None}
            )
        except ValidationError as err:
            _LOGGER.debug("Error parsing todo input fields: %s (%s)", item, str(err))
            raise vol.Invalid("Error parsing todo input fields") from err
        TodoStore(self._calendar).add(todo)
        await self._async_store()
        self._compute_state()
        await self.async_update_ha_state(force_refresh=True)

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update an item to the To-do list."""
        try:
            todo = Todo.parse_obj(
                {k: v for k, v in dataclasses.asdict(item).items() if v is not None}
            )
        except ValidationError as err:
            _LOGGER.debug("Error parsing todo input fields: %s (%s)", item, str(err))
            raise vol.Invalid("Error parsing todo input fields") from err
        TodoStore(self._calendar).edit(todo.uid, todo)
        await self._async_store()
        self._compute_state()
        await self.async_update_ha_state(force_refresh=True)

    async def async_delete_todo_items(self, uids: set[str]) -> None:
        """Add an item to the To-do list."""
        store = TodoStore(self._calendar)
        for uid in uids:
            store.delete(uid)
        await self._async_store()
        self._compute_state()
        await self.async_update_ha_state(force_refresh=True)

    async def async_move_todo_item(self, uid: str, previous: str | None = None) -> None:
        """Re-order an item to the To-do list."""
        if uid == previous:
            return
        # Build a map of each item id to its position within the list
        item_idx: dict[str, int] = {}
        todos = self._calendar.todos
        for idx, itm in enumerate(todos):
            item_idx[itm.uid] = idx
        if uid not in item_idx:
            raise HomeAssistantError(
                "Item '{uid}' not found in todo list {self.entity_id}"
            )
        if previous and previous not in item_idx:
            raise HomeAssistantError(
                "Item '{previous}' not found in todo list {self.entity_id}"
            )
        dst_idx = item_idx[previous] + 1 if previous else 0
        src_idx = item_idx[uid]
        src_item = todos.pop(src_idx)
        if dst_idx > src_idx:
            dst_idx -= 1
        todos.insert(dst_idx, src_item)
        self._calendar.todos = todos
        await self._async_store()
        self._compute_state()
        await self.async_update_ha_state(force_refresh=True)

    async def _async_store(self) -> None:
        """Persist the todo list to disk."""
        content = IcsCalendarStream.calendar_to_ics(self._calendar)
        await self._store.async_store(content)

    @property
    def _todo_items(self) -> list[TodoItem]:
        """Get the current set of To-do items."""
        results = []
        for item in self._calendar.todos:
            if item.status:
                status = ICS_TODO_STATUS_MAP.get(
                    item.status, TodoItemStatus.NEEDS_ACTION
                )
            else:
                status = TodoItemStatus.NEEDS_ACTION
            results.append(
                TodoItem(
                    summary=item.summary or "",
                    uid=item.uid,
                    status=status,
                )
            )
        return results

    def _compute_state(self) -> None:
        self._attr_incomplete_count = sum(
            item.status == TodoItemStatus.NEEDS_ACTION for item in self._todo_items
        )
