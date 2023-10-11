"""The todo integration."""

import dataclasses
import datetime
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ERR_NOT_FOUND, ERR_NOT_SUPPORTED
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, TodoItemStatus, TodoListEntityFeature

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(seconds=60)

ENTITY_ID_FORMAT = DOMAIN + ".{}"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Todo entities."""
    component = hass.data[DOMAIN] = EntityComponent[TodoListEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    websocket_api.async_register_command(hass, websocket_handle_todo_item_list)
    websocket_api.async_register_command(hass, websocket_handle_todo_item_create)
    websocket_api.async_register_command(hass, websocket_handle_todo_item_delete)
    websocket_api.async_register_command(hass, websocket_handle_todo_item_update)
    websocket_api.async_register_command(hass, websocket_handle_todo_item_move)

    await component.async_setup(config)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[TodoListEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[TodoListEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


@dataclasses.dataclass
class TodoItem:
    """A To-do item in a To-do list."""

    summary: str
    """The summary that represents the item."""

    uid: str | None = None
    """A unique identifier for the To-do item."""

    status: TodoItemStatus = TodoItemStatus.NEEDS_ACTION
    """A status or confirmation of the To-do item."""


class TodoListEntity(Entity):
    """An entity that represents a To-do list."""

    _attr_todo_items: list[TodoItem] | None = None

    @property
    def state(self) -> int | None:
        """Return the entity state as the count of incomplete items."""
        items = self.todo_items
        if items is None:
            return None
        return sum([item.status == TodoItemStatus.NEEDS_ACTION for item in items])

    @property
    def todo_items(self) -> list[TodoItem] | None:
        """Return the To-do items in the To-do list."""
        return self._attr_todo_items

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an item to the To-do list."""
        raise NotImplementedError()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update an item in the To-do list."""
        raise NotImplementedError()

    async def async_delete_todo_items(self, uids: set[str]) -> None:
        """Delete an item in the To-do list."""
        raise NotImplementedError()

    async def async_move_todo_item(self, uid: str, previous: str | None) -> None:
        """Move an item in the To-do list."""
        raise NotImplementedError()


@websocket_api.websocket_command(
    {
        vol.Required("type"): "todo/item/list",
        vol.Required("entity_id"): cv.entity_id,
    }
)
@websocket_api.async_response
async def websocket_handle_todo_item_list(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle the list of To-do items in a To-do- list."""
    component: EntityComponent[TodoListEntity] = hass.data[DOMAIN]
    if (
        not (entity_id := msg[CONF_ENTITY_ID])
        or not (entity := component.get_entity(entity_id))
        or not isinstance(entity, TodoListEntity)
    ):
        connection.send_error(msg["id"], ERR_NOT_FOUND, "Entity not found")
        return

    items: list[TodoItem] = entity.todo_items or []
    connection.send_message(
        websocket_api.result_message(
            msg["id"], {"items": [dataclasses.asdict(item) for item in items]}
        )
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "todo/item/create",
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("item"): vol.Schema(
            {
                vol.Required("summary"): cv.string,
                vol.Optional("status", default=TodoItemStatus.NEEDS_ACTION): vol.In(
                    {TodoItemStatus.NEEDS_ACTION, TodoItemStatus.COMPLETED}
                ),
            },
        ),
    }
)
@websocket_api.async_response
async def websocket_handle_todo_item_create(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle creation of a To-do item on a To-do list."""
    component: EntityComponent[TodoListEntity] = hass.data[DOMAIN]
    if not (entity := component.get_entity(msg["entity_id"])):
        connection.send_error(msg["id"], ERR_NOT_FOUND, "Entity not found")
        return

    if (
        not entity.supported_features
        or not entity.supported_features & TodoListEntityFeature.CREATE_TODO_ITEM
    ):
        connection.send_message(
            websocket_api.error_message(
                msg["id"],
                ERR_NOT_SUPPORTED,
                "To-do list does not support To-do item creation",
            )
        )
        return

    item = msg["item"]
    try:
        await entity.async_create_todo_item(
            item=TodoItem(summary=item["summary"], status=item["status"])
        )
    except HomeAssistantError as ex:
        connection.send_error(msg["id"], "failed", str(ex))
    else:
        connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "todo/item/delete",
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("uids"): vol.All(
            cv.ensure_list,
            [cv.string],
        ),
    }
)
@websocket_api.async_response
async def websocket_handle_todo_item_delete(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle deletion of a To-do item on a To-do list."""
    component: EntityComponent[TodoListEntity] = hass.data[DOMAIN]
    if not (entity := component.get_entity(msg["entity_id"])):
        connection.send_error(msg["id"], ERR_NOT_FOUND, "Entity not found")
        return

    if (
        not entity.supported_features
        or not entity.supported_features & TodoListEntityFeature.DELETE_TODO_ITEM
    ):
        connection.send_message(
            websocket_api.error_message(
                msg["id"],
                ERR_NOT_SUPPORTED,
                "To-do list does not support To-do item deletion",
            )
        )
        return

    try:
        await entity.async_delete_todo_items(uids=set(msg["uids"]))
    except HomeAssistantError as ex:
        connection.send_error(msg["id"], "failed", str(ex))
    else:
        connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "todo/item/update",
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("item"): vol.Schema(
            {
                vol.Required("uid"): cv.string,
                vol.Required("summary"): cv.string,
                vol.Optional("status"): vol.In(
                    {TodoItemStatus.NEEDS_ACTION, TodoItemStatus.COMPLETED}
                ),
            },
        ),
    }
)
@websocket_api.async_response
async def websocket_handle_todo_item_update(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle update of a To-do item on a To-do list."""
    component: EntityComponent[TodoListEntity] = hass.data[DOMAIN]
    if not (entity := component.get_entity(msg["entity_id"])):
        connection.send_error(msg["id"], ERR_NOT_FOUND, "Entity not found")
        return

    if (
        not entity.supported_features
        or not entity.supported_features & TodoListEntityFeature.UPDATE_TODO_ITEM
    ):
        connection.send_message(
            websocket_api.error_message(
                msg["id"],
                ERR_NOT_SUPPORTED,
                "To-do list does not support To-do item update",
            )
        )
        return

    try:
        await entity.async_update_todo_item(item=TodoItem(**msg["item"]))
    except HomeAssistantError as ex:
        connection.send_error(msg["id"], "failed", str(ex))
    else:
        connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "todo/item/move",
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("uid"): cv.string,
        vol.Optional("previous"): cv.string,
    }
)
@websocket_api.async_response
async def websocket_handle_todo_item_move(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle move of a To-do item within a To-do list."""
    component: EntityComponent[TodoListEntity] = hass.data[DOMAIN]
    if not (entity := component.get_entity(msg["entity_id"])):
        connection.send_error(msg["id"], ERR_NOT_FOUND, "Entity not found")
        return

    if (
        not entity.supported_features
        or not entity.supported_features & TodoListEntityFeature.MOVE_TODO_ITEM
    ):
        connection.send_message(
            websocket_api.error_message(
                msg["id"],
                ERR_NOT_SUPPORTED,
                "To-do list does not support To-do item reordering",
            )
        )
        return

    try:
        await entity.async_move_todo_item(uid=msg["uid"], previous=msg.get("previous"))
    except HomeAssistantError as ex:
        connection.send_error(msg["id"], "failed", str(ex))
    else:
        connection.send_result(msg["id"])
