"""Platform for sensor integration."""
from __future__ import annotations
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from . import ShoppingData
from .const import DOMAIN, EVENT_SHOPPING_LIST_UPDATED


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_devices: AddEntitiesCallback,
) -> None:
    """Set up entry."""
    async_add_devices([ShoppingListTotalSensor(), ShoppingListIncompleteSensor()])


class ShoppingListTotalSensor(SensorEntity):
    """Sensor to count the number of items in the shopping list"""

    def __init__(self) -> None:
        self._attr_unique_id = "shopping_list_total"
        self._attr_name = "Shopping List Total Items"
        self._attr_native_value = 0
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_should_poll = False
        self._attr_icon = "mdi:format-list-group"

    async def async_added_to_hass(self) -> None:
        """Register device notification."""
        self.hass.bus.async_listen(EVENT_SHOPPING_LIST_UPDATED, self.handle_update)
        self.handle_update(None)

    def handle_update(self, _):
        """Handles the List update event and published new total"""
        shopping: ShoppingData = self.hass.data[DOMAIN]
        self._attr_native_value = len(shopping.items)
        self.schedule_update_ha_state()


class ShoppingListIncompleteSensor(SensorEntity):
    """Sensor to count the number of items in the shopping list"""

    def __init__(self) -> None:
        self._attr_unique_id = "shopping_list_incomplete"
        self._attr_name = "Shopping List Incomplete Items"
        self._attr_native_value = 0
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_should_poll = False
        self._attr_icon = "mdi:format-list-group"

    async def async_added_to_hass(self) -> None:
        """Register device notification."""
        self.hass.bus.async_listen(EVENT_SHOPPING_LIST_UPDATED, self.handle_update)
        self.handle_update(None)

    def handle_update(self, _):
        """Handles the List update event and published new total"""
        shopping: ShoppingData = self.hass.data[DOMAIN]
        self._attr_native_value = len(
            [item for item in shopping.items if item["complete"] is False]
        )
        self.schedule_update_ha_state()
