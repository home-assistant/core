"""Constants for the To-do integration."""

from enum import IntFlag, StrEnum

DOMAIN = "todo"

ATTR_DUE = "due"
ATTR_DUE_DATE = "due_date"
ATTR_DUE_DATE_TIME = "due_date_time"
ATTR_DESCRIPTION = "description"


class TodoListEntityFeature(IntFlag):
    """Supported features of the To-do List entity."""

    CREATE_TODO_ITEM = 1
    DELETE_TODO_ITEM = 2
    UPDATE_TODO_ITEM = 4
    MOVE_TODO_ITEM = 8
    DUE_DATE = 16
    DUE_DATETIME = 32
    DESCRIPTION = 64


class TodoItemStatus(StrEnum):
    """Status or confirmation of a To-do List Item.

    This is a subset of the statuses supported in rfc5545.
    """

    NEEDS_ACTION = "needs_action"
    COMPLETED = "completed"
