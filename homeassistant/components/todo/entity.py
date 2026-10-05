"""Entity for the todo integration."""

from collections.abc import Callable, Iterable
import copy
import dataclasses
import datetime
from typing import Any, final, override

from propcache.api import cached_property

from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.entity import Entity

from .const import TodoItemStatus


@dataclasses.dataclass
class TodoItem:
    """A To-do item in a To-do list."""

    summary: str | None = None
    """The summary that represents the item."""

    uid: str | None = None
    """A unique identifier for the To-do item."""

    status: TodoItemStatus | None = None
    """A status or confirmation of the To-do item."""

    due: datetime.date | datetime.datetime | None = None
    """The date and time that a to-do is expected to be completed."""

    description: str | None = None
    """A more complete description than that provided by the summary."""

    completed: datetime.datetime | None = None
    """The date and time that a to-do item was marked completed."""


_TODO_ITEM_FIELD_NAMES: tuple[str, ...] = tuple(
    field.name for field in dataclasses.fields(TodoItem)
)


def serialize_todo_item(item: TodoItem) -> dict[str, Any]:
    """Serialize a To-do item for websocket subscribers.

    Avoids dataclasses.asdict(), which recursively deepcopies every field value
    (including the status StrEnum via __deepcopy__) on every subscriber update.
    TodoItem is a flat dataclass of immutable values, so a shallow dict is
    equivalent and far cheaper.
    """
    return {name: getattr(item, name) for name in _TODO_ITEM_FIELD_NAMES}


CACHED_PROPERTIES_WITH_ATTR_ = {
    "todo_items",
}


class TodoListEntity(Entity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """An entity that represents a To-do list."""

    _attr_todo_items: list[TodoItem] | None = None
    _update_listeners: list[Callable[[list[TodoItem] | None], None]] | None = None
    _last_broadcast_items: list[TodoItem] | None = None

    @property
    @override
    def state(self) -> int | None:
        """Return the entity state as the count of incomplete items."""
        items = self.todo_items
        if items is None:
            return None
        return sum([item.status == TodoItemStatus.NEEDS_ACTION for item in items])

    @cached_property
    def todo_items(self) -> list[TodoItem] | None:
        """Return the To-do items in the To-do list."""
        return self._attr_todo_items

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an item to the To-do list."""
        raise NotImplementedError

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update an item in the To-do list."""
        raise NotImplementedError

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete an item in the To-do list."""
        raise NotImplementedError

    async def async_move_todo_item(
        self, uid: str, previous_uid: str | None = None
    ) -> None:
        """Move an item in the To-do list.

        The To-do item with the specified `uid` should be moved to the position
        in the list after the specified by `previous_uid` or `None` for the first
        position in the To-do list.
        """
        raise NotImplementedError

    @final
    @callback
    def async_subscribe_updates(
        self, listener: Callable[[list[TodoItem] | None], None]
    ) -> CALLBACK_TYPE:
        """Subscribe to To-do list item updates."""
        if self._update_listeners is None:
            self._update_listeners = []
        self._update_listeners.append(listener)

        @callback
        def unsubscribe() -> None:
            if self._update_listeners:
                self._update_listeners.remove(listener)

        return unsubscribe

    @final
    @callback
    def async_update_listeners(self) -> None:
        """Push updated To-do items to all listeners."""
        items = self.todo_items
        if items == self._last_broadcast_items:
            return
        self._last_broadcast_items = (
            [copy.copy(item) for item in items] if items is not None else None
        )
        if not self._update_listeners:
            return
        for listener in self._update_listeners:
            listener(self._last_broadcast_items)

    @callback
    @override
    def _async_write_ha_state(self) -> None:
        """Notify to-do item subscribers."""
        super()._async_write_ha_state()
        self.async_update_listeners()


def api_items_factory(obj: Iterable[tuple[str, Any]]) -> dict[str, str]:
    """Convert TodoItem dataclass items to dictionary of attributes."""
    result: dict[str, str] = {}
    for name, value in obj:
        if value is None:
            continue
        if isinstance(value, (datetime.date, datetime.datetime)):
            result[name] = value.isoformat()
        else:
            result[name] = str(value)
    return result
