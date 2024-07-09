"""Constants for the To-do integration."""

from enum import IntFlag, StrEnum

DOMAIN = "todo"

ATTR_DUE = "due"
ATTR_DUE_DATE = "due_date"
ATTR_DUE_DATETIME = "due_datetime"
ATTR_DESCRIPTION = "description"
ATTR_ITEM = "item"
ATTR_RENAME = "rename"
ATTR_STATUS = "status"
SERVICE_ADD_ITEM = "add_item"
SERVICE_UPDATE_ITEM = "update_item"
SERVICE_REMOVE_ITEM = "remove_item"
SERVICE_GET_ITEMS = "get_items"
SERVICE_REMOVE_COMPLETED_ITEMS = "remove_completed_items"


class TodoListEntityFeature(IntFlag):
    """Supported features of the To-do List entity."""

    CREATE_TODO_ITEM = 1
    DELETE_TODO_ITEM = 2
    UPDATE_TODO_ITEM = 4
    MOVE_TODO_ITEM = 8
    SET_DUE_DATE_ON_ITEM = 16
    SET_DUE_DATETIME_ON_ITEM = 32
    SET_DESCRIPTION_ON_ITEM = 64


class TodoItemStatus(StrEnum):
    """Status or confirmation of a To-do List Item.

    This is a subset of the statuses supported in rfc5545.
    """

    NEEDS_ACTION = "needs_action"
    COMPLETED = "completed"
