"""Services for the todo integration."""

from collections.abc import Callable
import dataclasses
from typing import Any

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import (
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
from .entity import TodoItem, TodoListEntity, api_items_factory


@dataclasses.dataclass
class TodoItemFieldDescription:
    """A description of To-do item fields and validation requirements."""

    service_field: str
    """Field name for service calls."""

    todo_item_field: str
    """Field name for TodoItem."""

    validation: Callable[[Any], Any]
    """Probatio validation function."""

    required_feature: TodoListEntityFeature
    """Entity feature that enables this field."""


TODO_ITEM_FIELDS = [
    TodoItemFieldDescription(
        service_field=ATTR_DUE_DATE,
        validation=probatio.Any(cv.date, None),
        todo_item_field=ATTR_DUE,
        required_feature=TodoListEntityFeature.SET_DUE_DATE_ON_ITEM,
    ),
    TodoItemFieldDescription(
        service_field=ATTR_DUE_DATETIME,
        validation=probatio.Any(probatio.All(cv.datetime, dt_util.as_local), None),
        todo_item_field=ATTR_DUE,
        required_feature=TodoListEntityFeature.SET_DUE_DATETIME_ON_ITEM,
    ),
    TodoItemFieldDescription(
        service_field=ATTR_DESCRIPTION,
        validation=probatio.Any(cv.string, None),
        todo_item_field=ATTR_DESCRIPTION,
        required_feature=TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM,
    ),
]


TODO_ITEM_FIELD_SCHEMA = {
    probatio.Optional(desc.service_field): desc.validation for desc in TODO_ITEM_FIELDS
}


TODO_ITEM_FIELD_VALIDATIONS = [cv.has_at_most_one_key(ATTR_DUE_DATE, ATTR_DUE_DATETIME)]


TODO_SERVICE_GET_ITEMS_SCHEMA = {
    probatio.Optional(ATTR_STATUS): probatio.All(
        probatio.EnsureList(),
        [probatio.In({TodoItemStatus.NEEDS_ACTION, TodoItemStatus.COMPLETED})],
    ),
}


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
            dataclasses.asdict(item, dict_factory=api_items_factory)
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


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the todo services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        TodoServices.ADD_ITEM,
        probatio.All(
            cv.make_entity_service_schema(
                {
                    probatio.Required(ATTR_ITEM): probatio.All(
                        cv.string, str.strip, probatio.Length(min=1)
                    ),
                    **TODO_ITEM_FIELD_SCHEMA,
                }
            ),
            *TODO_ITEM_FIELD_VALIDATIONS,
        ),
        _async_add_todo_item,
        required_features=[TodoListEntityFeature.CREATE_TODO_ITEM],
    )
    component.async_register_entity_service(
        TodoServices.UPDATE_ITEM,
        probatio.All(
            cv.make_entity_service_schema(
                {
                    probatio.Required(ATTR_ITEM): probatio.All(
                        cv.string, probatio.Length(min=1)
                    ),
                    probatio.Optional(ATTR_RENAME): probatio.All(
                        cv.string, str.strip, probatio.Length(min=1)
                    ),
                    probatio.Optional(ATTR_STATUS): probatio.In(
                        {TodoItemStatus.NEEDS_ACTION, TodoItemStatus.COMPLETED},
                    ),
                    **TODO_ITEM_FIELD_SCHEMA,
                }
            ),
            *TODO_ITEM_FIELD_VALIDATIONS,
            cv.has_at_least_one_key(
                ATTR_RENAME,
                ATTR_STATUS,
                *[desc.service_field for desc in TODO_ITEM_FIELDS],
            ),
        ),
        _async_update_todo_item,
        required_features=[TodoListEntityFeature.UPDATE_TODO_ITEM],
    )
    component.async_register_entity_service(
        TodoServices.REMOVE_ITEM,
        cv.make_entity_service_schema(
            {
                probatio.Required(ATTR_ITEM): probatio.All(
                    probatio.EnsureList(), [cv.string]
                ),
            }
        ),
        _async_remove_todo_items,
        required_features=[TodoListEntityFeature.DELETE_TODO_ITEM],
    )
    component.async_register_entity_service(
        TodoServices.GET_ITEMS,
        cv.make_entity_service_schema(TODO_SERVICE_GET_ITEMS_SCHEMA),
        _async_get_todo_items,
        supports_response=SupportsResponse.ONLY,
    )
    component.async_register_entity_service(
        TodoServices.REMOVE_COMPLETED_ITEMS,
        None,
        _async_remove_completed_items,
        required_features=[TodoListEntityFeature.DELETE_TODO_ITEM],
    )
