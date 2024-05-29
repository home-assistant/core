"""The todo integration."""

from collections.abc import Callable, Iterable
import dataclasses
import datetime
from functools import cached_property
import logging
from typing import Any, final

import voluptuous as vol

from homeassistant.components import frontend, websocket_api
from homeassistant.components.websocket_api import ERR_NOT_FOUND, ERR_NOT_SUPPORTED
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import (
    CALLBACK_TYPE,
    HomeAssistant,
    ServiceCall,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonValueType

from .const import (
    ATTR_DESCRIPTION,
    ATTR_DUE,
    ATTR_DUE_DATE,
    ATTR_DUE_DATETIME,
    DOMAIN,
    TodoItemStatus,
    TodoListEntityFeature,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(seconds=60)

ENTITY_ID_FORMAT = DOMAIN + ".{}"


@dataclasses.dataclass
class TodoItemFieldDescription:
    """A description of To-do item fields and validation requirements."""

    service_field: str
    """Field name for service calls."""

    todo_item_field: str
    """Field name for TodoItem."""

    validation: Callable[[Any], Any]
    """Voluptuous validation function."""

    required_feature: TodoListEntityFeature
    """Entity feature that enables this field."""


TODO_ITEM_FIELDS = [
    TodoItemFieldDescription(
        service_field=ATTR_DUE_DATE,
        validation=vol.Any(cv.date, None),
        todo_item_field=ATTR_DUE,
        required_feature=TodoListEntityFeature.SET_DUE_DATE_ON_ITEM,
    ),
    TodoItemFieldDescription(
        service_field=ATTR_DUE_DATETIME,
        validation=vol.Any(vol.All(cv.datetime, dt_util.as_local), None),
        todo_item_field=ATTR_DUE,
        required_feature=TodoListEntityFeature.SET_DUE_DATETIME_ON_ITEM,
    ),
    TodoItemFieldDescription(
        service_field=ATTR_DESCRIPTION,
        validation=vol.Any(cv.string, None),
        todo_item_field=ATTR_DESCRIPTION,
        required_feature=TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM,
    ),
]

TODO_ITEM_FIELD_SCHEMA = {
    vol.Optional(desc.service_field): desc.validation for desc in TODO_ITEM_FIELDS
}
TODO_ITEM_FIELD_VALIDATIONS = [cv.has_at_most_one_key(ATTR_DUE_DATE, ATTR_DUE_DATETIME)]


def _validate_supported_features(
    supported_features: int | None, call_data: dict[str, Any]
) -> None:
    """Validate service call fields against entity supported features."""
    for desc in TODO_ITEM_FIELDS:
        if desc.service_field not in call_data:
            continue
        if not supported_features or not supported_features & desc.required_feature:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="update_field_not_supported",
                translation_placeholders={"service_field": desc.service_field},
            )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Todo entities."""
    component = hass.data[DOMAIN] = EntityComponent[TodoListEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    frontend.async_register_built_in_panel(hass, "todo", "todo", "mdi:clipboard-list")

    websocket_api.async_register_command(hass, websocket_handle_subscribe_todo_items)
    websocket_api.async_register_command(hass, websocket_handle_todo_item_list)
    websocket_api.async_register_command(hass, websocket_handle_todo_item_move)

    component.async_register_entity_service(
        "add_item",
        vol.All(
            cv.make_entity_service_schema(
                {
                    vol.Required("item"): vol.All(cv.string, vol.Length(min=1)),
                    **TODO_ITEM_FIELD_SCHEMA,
                }
            ),
            *TODO_ITEM_FIELD_VALIDATIONS,
        ),
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
                        {TodoItemStatus.NEEDS_ACTION, TodoItemStatus.COMPLETED},
                    ),
                    **TODO_ITEM_FIELD_SCHEMA,
                }
            ),
            *TODO_ITEM_FIELD_VALIDATIONS,
            cv.has_at_least_one_key(
                "rename", "status", *[desc.service_field for desc in TODO_ITEM_FIELDS]
            ),
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
    component.async_register_entity_service(
        "get_items",
        cv.make_entity_service_schema(
            {
                vol.Optional("status"): vol.All(
                    cv.ensure_list,
                    [vol.In({TodoItemStatus.NEEDS_ACTION, TodoItemStatus.COMPLETED})],
                ),
            }
        ),
        _async_get_todo_items,
        supports_response=SupportsResponse.ONLY,
    )
    component.async_register_entity_service(
        "remove_completed_items",
        {},
        _async_remove_completed_items,
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

    due: datetime.date | datetime.datetime | None = None
    """The date and time that a to-do is expected to be completed.

    This field may be a date or datetime depending whether the entity feature
    DUE_DATE or DUE_DATETIME are set.
    """

    description: str | None = None
    """A more complete description of than that provided by the summary.

    This field may be set when TodoListEntityFeature.DESCRIPTION is supported by
    the entity.
    """


CACHED_PROPERTIES_WITH_ATTR_ = {
    "todo_items",
}


class TodoListEntity(Entity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """An entity that represents a To-do list."""

    _attr_todo_items: list[TodoItem] | None = None
    _update_listeners: list[Callable[[list[JsonValueType] | None], None]] | None = None

    @property
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
        self,
        listener: Callable[[list[JsonValueType] | None], None],
    ) -> CALLBACK_TYPE:
        """Subscribe to To-do list item updates.

        Called by websocket API.
        """
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
        if not self._update_listeners:
            return

        todo_items: list[JsonValueType] = [
            dataclasses.asdict(item) for item in self.todo_items or ()
        ]
        for listener in self._update_listeners:
            listener(todo_items)

    @callback
    def _async_write_ha_state(self) -> None:
        """Notify to-do item subscribers."""
        super()._async_write_ha_state()
        self.async_update_listeners()


@websocket_api.websocket_command(
    {
        vol.Required("type"): "todo/item/subscribe",
        vol.Required("entity_id"): cv.entity_domain(DOMAIN),
    }
)
@websocket_api.async_response
async def websocket_handle_subscribe_todo_items(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Subscribe to To-do list item updates."""
    component: EntityComponent[TodoListEntity] = hass.data[DOMAIN]
    entity_id: str = msg["entity_id"]

    if not (entity := component.get_entity(entity_id)):
        connection.send_error(
            msg["id"],
            "invalid_entity_id",
            f"To-do list entity not found: {entity_id}",
        )
        return

    @callback
    def todo_item_listener(todo_items: list[JsonValueType] | None) -> None:
        """Push updated To-do list items to websocket."""
        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                {
                    "items": todo_items,
                },
            )
        )

    connection.subscriptions[msg["id"]] = entity.async_subscribe_updates(
        todo_item_listener
    )
    connection.send_result(msg["id"])

    # Push an initial forecast update
    entity.async_update_listeners()


def _api_items_factory(obj: Iterable[tuple[str, Any]]) -> dict[str, str]:
    """Convert CalendarEvent dataclass items to dictionary of attributes."""
    result: dict[str, str] = {}
    for name, value in obj:
        if value is None:
            continue
        if isinstance(value, (datetime.date, datetime.datetime)):
            result[name] = value.isoformat()
        else:
            result[name] = str(value)
    return result


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
            msg["id"],
            {
                "items": [
                    dataclasses.asdict(item, dict_factory=_api_items_factory)
                    for item in items
                ]
            },
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
    _validate_supported_features(entity.supported_features, call.data)
    await entity.async_create_todo_item(
        item=TodoItem(
            summary=call.data["item"],
            status=TodoItemStatus.NEEDS_ACTION,
            **{
                desc.todo_item_field: call.data[desc.service_field]
                for desc in TODO_ITEM_FIELDS
                if desc.service_field in call.data
            },
        )
    )


async def _async_update_todo_item(entity: TodoListEntity, call: ServiceCall) -> None:
    """Update an item in the To-do list."""
    item = call.data["item"]
    found = _find_by_uid_or_summary(item, entity.todo_items)
    if not found:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="item_not_found",
            translation_placeholders={"item": item},
        )

    _validate_supported_features(entity.supported_features, call.data)

    # Perform a partial update on the existing entity based on the fields
    # present in the update. This allows explicitly clearing any of the
    # extended fields present and set to None.
    updated_data = dataclasses.asdict(found)
    if summary := call.data.get("rename"):
        updated_data["summary"] = summary
    if status := call.data.get("status"):
        updated_data["status"] = status
    updated_data.update(
        {
            desc.todo_item_field: call.data[desc.service_field]
            for desc in TODO_ITEM_FIELDS
            if desc.service_field in call.data
        }
    )
    await entity.async_update_todo_item(item=TodoItem(**updated_data))


async def _async_remove_todo_items(entity: TodoListEntity, call: ServiceCall) -> None:
    """Remove an item in the To-do list."""
    uids = []
    for item in call.data.get("item", []):
        found = _find_by_uid_or_summary(item, entity.todo_items)
        if not found or not found.uid:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="item_not_found",
                translation_placeholders={"item": item},
            )
        uids.append(found.uid)
    await entity.async_delete_todo_items(uids=uids)


async def _async_get_todo_items(
    entity: TodoListEntity, call: ServiceCall
) -> dict[str, Any]:
    """Return items in the To-do list."""
    return {
        "items": [
            dataclasses.asdict(item, dict_factory=_api_items_factory)
            for item in entity.todo_items or ()
            if not (statuses := call.data.get("status")) or item.status in statuses
        ]
    }


async def _async_remove_completed_items(entity: TodoListEntity, _: ServiceCall) -> None:
    """Remove all completed items from the To-do list."""
    uids = [
        item.uid
        for item in entity.todo_items or ()
        if item.status == TodoItemStatus.COMPLETED and item.uid
    ]
    if uids:
        await entity.async_delete_todo_items(uids=uids)
