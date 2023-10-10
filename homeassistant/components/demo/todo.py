"""Demo platform that offers a fake todo entity."""

import logging

from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the demo todo platform."""
    async_add_entities([DemoTodoListEntity()])


class DemoTodoListEntity(TodoListEntity):
    """Representation of a demo todo list entity."""

    _attr_has_entity_name = True
    _attr_name = "Reminders"
    _attr_should_poll = False

    @property
    def todo_items(self) -> list[TodoItem]:
        """Get items in the To-do list."""
        return [
            TodoItem(summary="Item #1", uid="1", status=TodoItemStatus.NEEDS_ACTION),
            TodoItem(summary="Item #2", uid="2", status=TodoItemStatus.COMPLETED),
        ]
