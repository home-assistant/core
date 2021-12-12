"""Support for Ridwell sensors."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from aioridwell.client import RidwellAccount, RidwellPickupEvent

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_DATE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DATA_ACCOUNT, DATA_COORDINATOR, DOMAIN

ATTR_CATEGORY = "category"
ATTR_PICKUP_STATE = "pickup_state"
ATTR_PICKUP_TYPES = "pickup_types"
ATTR_QUANTITY = "quantity"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up WattTime sensors based on a config entry."""
    accounts = hass.data[DOMAIN][entry.entry_id][DATA_ACCOUNT]
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities(
        [RidwellSensor(coordinator, account) for account in accounts.values()]
    )


class RidwellSensor(CoordinatorEntity, SensorEntity):
    """Define a Ridwell pickup sensor."""

    _attr_device_class = DEVICE_CLASS_DATE

    def __init__(
        self, coordinator: DataUpdateCoordinator, account: RidwellAccount
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._account = account
        self._attr_name = f"Ridwell Pickup ({account.address['street1']})"
        self._attr_unique_id = account.account_id

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return entity specific state attributes."""
        event = self.coordinator.data[self._account.account_id]

        attrs: dict[str, Any] = {
            ATTR_PICKUP_TYPES: {},
            ATTR_PICKUP_STATE: event.state,
        }

        for pickup in event.pickups:
            if pickup.name not in attrs[ATTR_PICKUP_TYPES]:
                attrs[ATTR_PICKUP_TYPES][pickup.name] = {
                    ATTR_CATEGORY: pickup.category,
                    ATTR_QUANTITY: pickup.quantity,
                }
            else:
                # Ridwell's API will return distinct objects, even if they have the
                # same name (e.g. two pickups of Latex Paint will show up as two
                # objects) – so, we sum the quantities:
                attrs[ATTR_PICKUP_TYPES][pickup.name][ATTR_QUANTITY] += pickup.quantity

        return attrs

    @property
    def native_value(self) -> StateType | date | datetime:
        """Return the value reported by the sensor."""
        event: RidwellPickupEvent = self.coordinator.data[self._account.account_id]
        return event.pickup_date
