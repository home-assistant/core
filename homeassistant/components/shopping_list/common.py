"""Shopping list commons."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any, cast
import uuid

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.json import save_json
from homeassistant.util.json import JsonValueType, load_json_array

from .const import DOMAIN, EVENT_SHOPPING_LIST_UPDATED

_LOGGER = logging.getLogger(__name__)

ATTR_COMPLETE = "complete"

ITEM_UPDATE_SCHEMA = vol.Schema({ATTR_COMPLETE: bool, ATTR_NAME: str})
PERSISTENCE = ".shopping_list.json"


type ShoppingListConfigEntry = ConfigEntry[ShoppingData]


class NoMatchingShoppingListItem(Exception):
    """No matching item could be found in the shopping list."""


class ShoppingData:
    """Class to hold shopping list data."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the shopping list."""
        self.hass = hass
        self.items: list[dict[str, JsonValueType]] = []
        self._listeners: list[Callable[[], None]] = []

    async def async_add(
        self, name: str | None, complete: bool = False, context: Context | None = None
    ) -> dict[str, JsonValueType]:
        """Add a shopping list item."""
        item: dict[str, JsonValueType] = {
            "name": name,
            "id": uuid.uuid4().hex,
            "complete": complete,
        }
        self.items.append(item)
        await self.hass.async_add_executor_job(self.save)
        self._async_notify()
        self.hass.bus.async_fire(
            EVENT_SHOPPING_LIST_UPDATED,
            {"action": "add", "item": item},
            context=context,
        )
        return item

    async def async_remove(
        self, item_id: str, context: Context | None = None
    ) -> dict[str, JsonValueType] | None:
        """Remove a shopping list item."""
        removed = await self.async_remove_items(
            item_ids=set({item_id}), context=context
        )
        return next(iter(removed), None)

    async def async_remove_items(
        self, item_ids: set[str], context: Context | None = None
    ) -> list[dict[str, JsonValueType]]:
        """Remove a shopping list item."""
        items_dict: dict[str, dict[str, JsonValueType]] = {}
        for itm in self.items:
            item_id = cast(str, itm["id"])
            items_dict[item_id] = itm
        removed = []
        for item_id in item_ids:
            _LOGGER.debug("Removing %s", item_id)
            if not (item := items_dict.pop(item_id, None)):
                raise NoMatchingShoppingListItem(
                    f"Item '{item_id}' not found in shopping list"
                )
            removed.append(item)
        self.items = list(items_dict.values())
        await self.hass.async_add_executor_job(self.save)
        self._async_notify()
        for item in removed:
            self.hass.bus.async_fire(
                EVENT_SHOPPING_LIST_UPDATED,
                {"action": "remove", "item": item},
                context=context,
            )
        return removed

    async def async_complete(
        self, name: str, context: Context | None = None
    ) -> list[dict[str, JsonValueType]]:
        """Mark all shopping list items with the given name as complete."""
        complete_items = [
            item for item in self.items if item["name"] == name and not item["complete"]
        ]

        if len(complete_items) == 0:
            raise NoMatchingShoppingListItem(f"No items with name '{name}' found")

        for item in complete_items:
            _LOGGER.debug("Completing %s", item)
            item["complete"] = True
        await self.hass.async_add_executor_job(self.save)
        self._async_notify()
        for item in complete_items:
            self.hass.bus.async_fire(
                EVENT_SHOPPING_LIST_UPDATED,
                {"action": "complete", "item": item},
                context=context,
            )
        return complete_items

    async def async_update(
        self, item_id: str | None, info: dict[str, Any], context: Context | None = None
    ) -> dict[str, JsonValueType]:
        """Update a shopping list item."""
        item = next((itm for itm in self.items if itm["id"] == item_id), None)

        if item is None:
            raise NoMatchingShoppingListItem(
                f"Item '{item_id}' not found in shopping list"
            )

        info = ITEM_UPDATE_SCHEMA(info)
        item.update(info)
        await self.hass.async_add_executor_job(self.save)
        self._async_notify()
        self.hass.bus.async_fire(
            EVENT_SHOPPING_LIST_UPDATED,
            {"action": "update", "item": item},
            context=context,
        )
        return item

    async def async_clear_completed(self, context: Context | None = None) -> None:
        """Clear completed items."""
        self.items = [itm for itm in self.items if not itm["complete"]]
        await self.hass.async_add_executor_job(self.save)
        self._async_notify()
        self.hass.bus.async_fire(
            EVENT_SHOPPING_LIST_UPDATED,
            {"action": "clear"},
            context=context,
        )

    async def async_update_list(
        self, info: dict[str, JsonValueType], context: Context | None = None
    ) -> list[dict[str, JsonValueType]]:
        """Update all items in the list."""
        for item in self.items:
            item.update(info)
        await self.hass.async_add_executor_job(self.save)
        self._async_notify()
        self.hass.bus.async_fire(
            EVENT_SHOPPING_LIST_UPDATED,
            {"action": "update_list"},
            context=context,
        )
        return self.items

    async def async_reorder(
        self, item_ids: list[str], context: Context | None = None
    ) -> None:
        """Reorder items."""
        # The array for sorted items.
        new_items = []
        all_items_mapping = {item["id"]: item for item in self.items}
        # Append items by the order of passed in array.
        for item_id in item_ids:
            if item_id not in all_items_mapping:
                raise NoMatchingShoppingListItem(
                    f"Item '{item_id}' not found in shopping list"
                )
            new_items.append(all_items_mapping[item_id])
            # Remove the item from mapping after it's appended in the result array.
            del all_items_mapping[item_id]
        # Append the rest of the items
        for value in all_items_mapping.values():
            # All the unchecked items must be passed in the item_ids array,
            # so all items left in the mapping should be checked items.
            if value["complete"] is False:
                raise vol.Invalid(
                    "The item ids array doesn't contain all the unchecked shopping list"
                    " items."
                )
            new_items.append(value)
        self.items = new_items
        await self.hass.async_add_executor_job(self.save)
        self._async_notify()
        self.hass.bus.async_fire(
            EVENT_SHOPPING_LIST_UPDATED,
            {"action": "reorder"},
            context=context,
        )

    async def async_move_item(self, uid: str, previous: str | None = None) -> None:
        """Re-order a shopping list item."""
        if uid == previous:
            return
        item_idx = {cast(str, itm["id"]): idx for idx, itm in enumerate(self.items)}
        if uid not in item_idx:
            raise NoMatchingShoppingListItem(f"Item '{uid}' not found in shopping list")
        if previous and previous not in item_idx:
            raise NoMatchingShoppingListItem(
                f"Item '{previous}' not found in shopping list"
            )
        dst_idx = item_idx[previous] + 1 if previous else 0
        src_idx = item_idx[uid]
        src_item = self.items.pop(src_idx)
        if dst_idx > src_idx:
            dst_idx -= 1
        self.items.insert(dst_idx, src_item)
        await self.hass.async_add_executor_job(self.save)
        self._async_notify()
        self.hass.bus.async_fire(
            EVENT_SHOPPING_LIST_UPDATED,
            {"action": "reorder"},
        )

    async def async_sort(
        self, reverse: bool = False, context: Context | None = None
    ) -> None:
        """Sort items by name."""
        self.items = sorted(self.items, key=lambda item: item["name"], reverse=reverse)  # type: ignore[arg-type,return-value]
        await self.hass.async_add_executor_job(self.save)
        self._async_notify()
        self.hass.bus.async_fire(
            EVENT_SHOPPING_LIST_UPDATED,
            {"action": "sorted"},
            context=context,
        )

    async def async_load(self) -> None:
        """Load items."""

        def load() -> list[dict[str, JsonValueType]]:
            """Load the items synchronously."""
            return cast(
                list[dict[str, JsonValueType]],
                load_json_array(self.hass.config.path(PERSISTENCE)),
            )

        self.items = await self.hass.async_add_executor_job(load)

    def save(self) -> None:
        """Save the items."""
        save_json(self.hass.config.path(PERSISTENCE), self.items)

    def async_add_listener(self, cb: Callable[[], None]) -> Callable[[], None]:
        """Add a listener to notify when data is updated."""

        def unsub() -> None:
            self._listeners.remove(cb)

        self._listeners.append(cb)
        return unsub

    def _async_notify(self) -> None:
        """Notify all listeners that data has been updated."""
        for listener in self._listeners:
            listener()


def _get_shopping_data(hass: HomeAssistant) -> ShoppingData:
    entries: list[ShoppingListConfigEntry] = hass.config_entries.async_loaded_entries(
        DOMAIN
    )
    if not entries:
        raise HomeAssistantError("No shopping list config entry found")
    return entries[0].runtime_data
