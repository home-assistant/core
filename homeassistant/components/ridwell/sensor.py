"""Support for Ridwell sensors."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from aioridwell.client import RidwellAccount

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, DEVICE_CLASS_TIMESTAMP
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util.dt import as_utc

from .const import DATA_ACCOUNT, DATA_COORDINATOR, DOMAIN

ATTR_PICKUP_STATE = "pickup_state"
ATTR_PICKUP_TYPES = "pickup_types"

DEFAULT_ATTRIBUTION = "Pickup data provided by Ridwell"


@callback
def async_get_utc_midnight(target_date: date) -> datetime:
    """Get UTC midnight for a given date."""
    return as_utc(datetime.combine(target_date, datetime.min.time()))


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

    _attr_device_class = DEVICE_CLASS_TIMESTAMP

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
            ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION,
            ATTR_PICKUP_TYPES: {},
            ATTR_PICKUP_STATE: event.state,
        }

        for pickup in event.pickups:
            if pickup.name not in attrs[ATTR_PICKUP_TYPES]:
                attrs[ATTR_PICKUP_TYPES][pickup.name] = {
                    "category": pickup.category,
                    "quantity": pickup.quantity,
                }
            else:
                # Ridwell's API will return distinct objects, even if they have the
                # same name (e.g. two pickups of Latex Paint will show up as two
                # objects) – so, we sum the quantities:
                attrs[ATTR_PICKUP_TYPES][pickup.name]["quantity"] += pickup.quantity

        return attrs

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        event = self.coordinator.data[self._account.account_id]
        return async_get_utc_midnight(event.pickup_date).isoformat()
