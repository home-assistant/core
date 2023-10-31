"""The todo integration."""

import dataclasses
import datetime
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import frontend, websocket_api
from homeassistant.components.websocket_api import ERR_NOT_FOUND, ERR_NOT_SUPPORTED
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
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

    frontend.async_register_built_in_panel(hass, "todo", "todo", "mdi:clipboard-list")

    websocket_api.async_register_command(hass, websocket_handle_todo_item_list)
    websocket_api.async_register_command(hass, websocket_handle_todo_item_move)

    component.async_register_entity_service(
        "add_item",
        {
            vol.Required("item"): vol.All(cv.string, vol.Length(min=1)),
        },
        _async_add_todo_item,
        required_features=[TodoListEntityFeature.CREATE_TODO_ITEM],
    )
    component.async_register_entity_service(
        "update_item",
        vol.All(
            cv.make_entity_service_schema(
                {
                    vol.Required("item"): vol.All(cv.string, vol.Length(min=1)),
                    vol.Optional("rename"): vol.All(cv.string, vol.Length(min=1)),
                    vol.Optional("status"): vol.In(
                        {TodoItemStatus.NEEDS_ACTION, TodoItemStatus.COMPLETED}
                    ),
                }
            ),
            cv.has_at_least_one_key("rename", "status"),
        ),
        _async_update_todo_item,
        required_features=[TodoListEntityFeature.UPDATE_TODO_ITEM],
    )
    component.async_register_entity_service(
        "remove_item",
        cv.make_entity_service_schema(
            {
                vol.Required("item"): vol.All(cv.ensure_list, [cv.string]),
            }
        ),
        _async_remove_todo_items,
        required_features=[TodoListEntityFeature.DELETE_TODO_ITEM],
    )

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

    summary: str | None = None
    """The summary that represents the item."""

    uid: str | None = None
    """A unique identifier for the To-do item."""

    status: TodoItemStatus | None = None
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

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete an item in the To-do list."""
        raise NotImplementedError()

    async def async_move_todo_item(
        self, uid: str, previous_uid: str | None = None
    ) -> None:
        """Move an item in the To-do list.

        The To-do item with the specified `uid` should be moved to the position
        in the list after the specified by `previous_uid` or `None` for the first
        position in the To-do list.
        """
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
        vol.Required("type"): "todo/item/move",
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("uid"): cv.string,
        vol.Optional("previous_uid"): cv.string,
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
        await entity.async_move_todo_item(
            uid=msg["uid"], previous_uid=msg.get("previous_uid")
        )
    except HomeAssistantError as ex:
        connection.send_error(msg["id"], "failed", str(ex))
    else:
        connection.send_result(msg["id"])


def _find_by_uid_or_summary(
    value: str, items: list[TodoItem] | None
) -> TodoItem | None:
    """Find a To-do List item by uid or summary name."""
    for item in items or ():
        if value in (item.uid, item.summary):
            return item
    return None


async def _async_add_todo_item(entity: TodoListEntity, call: ServiceCall) -> None:
    """Add an item to the To-do list."""
    await entity.async_create_todo_item(
        item=TodoItem(summary=call.data["item"], status=TodoItemStatus.NEEDS_ACTION)
    )


async def _async_update_todo_item(entity: TodoListEntity, call: ServiceCall) -> None:
    """Update an item in the To-do list."""
    item = call.data["item"]
    found = _find_by_uid_or_summary(item, entity.todo_items)
    if not found:
        raise ValueError(f"Unable to find To-do item '{item}'")

    update_item = TodoItem(
        uid=found.uid, summary=call.data.get("rename"), status=call.data.get("status")
    )

    await entity.async_update_todo_item(item=update_item)


async def _async_remove_todo_items(entity: TodoListEntity, call: ServiceCall) -> None:
    """Remove an item in the To-do list."""
    uids = []
    for item in call.data.get("item", []):
        found = _find_by_uid_or_summary(item, entity.todo_items)
        if not found or not found.uid:
            raise ValueError(f"Unable to find To-do item '{item}")
        uids.append(found.uid)
    await entity.async_delete_todo_items(uids=uids)
