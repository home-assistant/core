"""The todo integration."""

import dataclasses
import datetime
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ERR_NOT_FOUND
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
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

TASK_ITEM_FIELDS = {
    vol.Required("summary"): vol.All(cv.string, vol.Length(min=1)),
    vol.Optional("status", default=TodoItemStatus.NEEDS_ACTION): vol.In(
        {TodoItemStatus.NEEDS_ACTION, TodoItemStatus.COMPLETED}
    ),
}
TASK_ITEM_UPDATE_FIELDS = {
    vol.Optional("uid"): cv.string,
    **TASK_ITEM_FIELDS,
}


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Todo entities."""
    component = hass.data[DOMAIN] = EntityComponent[TodoListEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    websocket_api.async_register_command(hass, websocket_handle_todo_item_list)

    component.async_register_entity_service(
        "create_item",
        TASK_ITEM_FIELDS,
        _async_create_todo_item,
        required_features=[TodoListEntityFeature.CREATE_TODO_ITEM],
    )
    component.async_register_entity_service(
        "update_item",
        vol.All(
            cv.make_entity_service_schema(TASK_ITEM_UPDATE_FIELDS),
            cv.has_at_least_one_key("uid", "summary"),
        ),
        _async_update_todo_item,
        required_features=[TodoListEntityFeature.UPDATE_TODO_ITEM],
    )
    component.async_register_entity_service(
        "delete_item",
        vol.All(
            cv.make_entity_service_schema(
                {
                    vol.Optional("uid"): vol.All(cv.ensure_list, [cv.string]),
                    vol.Optional("summary"): vol.All(cv.ensure_list, [cv.string]),
                }
            ),
            cv.has_at_least_one_key("uid", "summary"),
        ),
        _async_delete_todo_items,
        required_features=[TodoListEntityFeature.DELETE_TODO_ITEM],
    )
    component.async_register_entity_service(
        "move_item",
        vol.All(
            cv.make_entity_service_schema(
                {
                    vol.Optional("uid"): cv.string,
                    vol.Optional("summary"): cv.string,
                    vol.Optional("previous_uid"): cv.string,
                    vol.Optional("previous_summary"): cv.string,
                }
            ),
            cv.has_at_least_one_key("uid", "summary"),
            cv.has_at_most_one_key("uid", "summary"),
            cv.has_at_most_one_key("previous_uid", "previous_summary"),
            # Don't mix and match uid and summary across current and previous
            cv.has_at_most_one_key("uid", "previous_summary"),
            cv.has_at_most_one_key("summary", "previous_uid"),
        ),
        _async_move_todo_item,
        required_features=[TodoListEntityFeature.MOVE_TODO_ITEM],
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

    summary: str
    """The summary that represents the item."""

    uid: str | None = None
    """A unique identifier for the To-do item."""

    status: TodoItemStatus = TodoItemStatus.NEEDS_ACTION
    """A status or confirmation of the To-do item."""

    @classmethod
    def from_dict(cls, obj: dict[str, Any]) -> "TodoItem":
        """Create a To-do Item from a dictionary parsed by schema validators."""
        return cls(summary=obj["summary"], status=obj["status"], uid=obj.get("uid"))


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

    async def async_move_todo_item(self, uid: str, previous_uid: str | None) -> None:
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


def _find_by_summary(summary: str, items: list[TodoItem] | None) -> TodoItem | None:
    """Find a To-do List item by summary name."""
    for item in items or ():
        if item.summary == summary:
            return item
    return None


async def _async_create_todo_item(entity: TodoListEntity, call: ServiceCall) -> None:
    """Add an item to the To-do list."""
    await entity.async_create_todo_item(item=TodoItem.from_dict(call.data))


async def _async_update_todo_item(entity: TodoListEntity, call: ServiceCall) -> None:
    """Update an item in the To-do list."""
    item = TodoItem.from_dict(call.data)
    if not item.uid:
        found = _find_by_summary(item.summary, entity.todo_items)
        if not found:
            raise vol.Invalid(
                f"Unable to find To-do item with summary '{item.summary}'"
            )
        item.uid = found.uid

    await entity.async_update_todo_item(item=item)


async def _async_delete_todo_items(entity: TodoListEntity, call: ServiceCall) -> None:
    """Delete an item in the To-do list."""
    uids = call.data.get("uid", [])
    if not uids:
        summaries = call.data.get("summary", [])
        for summary in summaries:
            item = _find_by_summary(summary, entity.todo_items)
            if not item:
                raise vol.Invalid(f"Unable to find To-do item with summariy'{summary}")
            uids.append(item.uid)
    await entity.async_delete_todo_items(uids=uids)


async def _async_move_todo_item(entity: TodoListEntity, call: ServiceCall) -> None:
    """Move an item in the To-do list."""
    uid = call.data.get("uid", "")
    if not uid:
        summary = call.data["summary"]
        item = _find_by_summary(summary, entity.todo_items)
        if not item:
            raise vol.Invalid(f"Unable to find To-do item with summary '{summary}'")
        uid = item.uid
    previous_uid = call.data.get("previous_uid")
    if not previous_uid and (previous_summary := call.data.get("previous_summary")):
        item = _find_by_summary(previous_summary, entity.todo_items)
        if not item:
            raise vol.Invalid(
                f"Unable to find To-do item with summary '{previous_summary}'"
            )
        previous_uid = item.uid
    await entity.async_move_todo_item(uid=uid, previous_uid=previous_uid)
