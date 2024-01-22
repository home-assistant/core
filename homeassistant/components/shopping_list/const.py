"""All constants related to the shopping list component."""

from homeassistant.const import EVENT_SHOPPING_LIST_UPDATED  # noqa: F401

DOMAIN = "shopping_list"


ATTR_REVERSE = "reverse"

DEFAULT_REVERSE = False

SERVICE_ADD_ITEM = "add_item"
SERVICE_REMOVE_ITEM = "remove_item"
SERVICE_COMPLETE_ITEM = "complete_item"
SERVICE_INCOMPLETE_ITEM = "incomplete_item"
SERVICE_COMPLETE_ALL = "complete_all"
SERVICE_INCOMPLETE_ALL = "incomplete_all"
SERVICE_CLEAR_COMPLETED_ITEMS = "clear_completed_items"
SERVICE_SORT = "sort"
