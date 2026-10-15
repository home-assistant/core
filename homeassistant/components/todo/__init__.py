"""The todo integration."""

import dataclasses
import datetime
import logging
from typing import Any

import probatio

from homeassistant.components import frontend, websocket_api
from homeassistant.components.websocket_api import ERR_NOT_FOUND, ERR_NOT_SUPPORTED
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import (  # noqa: F401
    ATTR_DESCRIPTION,
    ATTR_DUE,
    ATTR_DUE_DATE,
    ATTR_DUE_DATETIME,
    ATTR_ITEM,
    ATTR_RENAME,
    ATTR_STATUS,
    DATA_COMPONENT,
    DOMAIN,
    TodoItemStatus,
    TodoListEntityFeature,
    TodoServices,
)
from .entity import TodoItem, TodoListEntity, api_items_factory, serialize_todo_item
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = datetime.timedelta(seconds=60)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Todo entities."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[TodoListEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    frontend.async_register_built_in_panel(hass, "todo", "todo", "mdi:clipboard-list")

    websocket_api.async_register_command(hass, websocket_handle_subscribe_todo_items)
    websocket_api.async_register_command(hass, websocket_handle_todo_item_list)
    websocket_api.async_register_command(hass, websocket_handle_todo_item_move)

    async_setup_services(hass)

    await component.async_setup(config)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "todo/item/subscribe",
        probatio.Required("entity_id"): cv.entity_domain(DOMAIN),
    }
)
@websocket_api.async_response
async def websocket_handle_subscribe_todo_items(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Subscribe to To-do list item updates."""
    entity_id: str = msg["entity_id"]

    if not (entity := hass.data[DATA_COMPONENT].get_entity(entity_id)):
        connection.send_error(
            msg["id"],
            "invalid_entity_id",
            f"To-do list entity not found: {entity_id}",
        )
        return

    @callback
    def todo_item_listener(todo_items: list[TodoItem] | None) -> None:
        """Push updated To-do list items to websocket."""
        items = [serialize_todo_item(item) for item in todo_items or []]
        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                {"items": items},
            )
        )

    connection.subscriptions[msg["id"]] = entity.async_subscribe_updates(
        todo_item_listener
    )
    connection.send_result(msg["id"])

    # Push an initial list update to the new subscriber only
    todo_item_listener(entity.todo_items)


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "todo/item/list",
        probatio.Required("entity_id"): cv.entity_id,
    }
)
@websocket_api.async_response
async def websocket_handle_todo_item_list(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle the list of To-do items in a To-do- list."""
    if (
        not (entity_id := msg[CONF_ENTITY_ID])
        or not (entity := hass.data[DATA_COMPONENT].get_entity(entity_id))
        or not isinstance(entity, TodoListEntity)
    ):
        connection.send_error(msg["id"], ERR_NOT_FOUND, "Entity not found")
        return

    items: list[TodoItem] = entity.todo_items or []
    connection.send_message(
        websocket_api.result_message(
            msg["id"],
            {
                "items": [
                    dataclasses.asdict(item, dict_factory=api_items_factory)
                    for item in items
                ]
            },
        )
    )


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "todo/item/move",
        probatio.Required("entity_id"): cv.entity_id,
        probatio.Required("uid"): cv.string,
        probatio.Optional("previous_uid"): cv.string,
    }
)
@websocket_api.async_response
async def websocket_handle_todo_item_move(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle move of a To-do item within a To-do list."""
    if not (entity := hass.data[DATA_COMPONENT].get_entity(msg["entity_id"])):
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
        await entity.async_move_todo_item(
            uid=msg["uid"], previous_uid=msg.get("previous_uid")
        )
    except HomeAssistantError as ex:
        connection.send_error(msg["id"], "failed", str(ex))
    else:
        connection.send_result(msg["id"])
