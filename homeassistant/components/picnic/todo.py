"""Definition of Picnic shopping cart."""
from __future__ import annotations

import logging
from typing import Any, cast

from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CONF_COORDINATOR, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Picnic shopping cart todo platform config entry."""
    picnic_coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR]

    # Add an entity shopping card
    async_add_entities([PicnicCart(picnic_coordinator, config_entry)])


class PicnicCart(TodoListEntity, CoordinatorEntity):
    """A Picnic Shopping Cart TodoListEntity."""

    _attr_has_entity_name = True
    _attr_translation_key = "shopping_cart"
    _attr_icon = "mdi:cart"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Any],
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize PicnicCart."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, cast(str, config_entry.unique_id))},
            manufacturer="Picnic",
            model=config_entry.unique_id,
        )
        self._attr_unique_id = f"{config_entry.unique_id}-cart"

    @property
    def todo_items(self) -> list[TodoItem] | None:
        """Get the current set of items in cart items."""
        if self.coordinator.data is None:
            return None

        _LOGGER.debug(self.coordinator.data["cart_data"]["items"])

        items = []
        for item in self.coordinator.data["cart_data"]["items"]:
            for article in item["items"]:
                items.append(
                    TodoItem(
                        summary=f"{article['name']} ({article['unit_quantity']})",
                        uid=f"{item['id']}-{article['id']}",
                        status=TodoItemStatus.NEEDS_ACTION,  # We set 'NEEDS_ACTION' so they count as state
                    )
                )

        return items
