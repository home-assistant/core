"""Support for Ridwell sensors."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from aioridwell.client import RidwellAccount, RidwellPickup

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

from .const import DATA_ACCOUNT, DATA_COORDINATOR, DOMAIN, LOGGER

ATTR_PICKUP_TYPES = "pickup_types"
ATTR_ROTATING_CATEGORY = "rotating_category"

DEFAULT_ATTRIBUTION = "Pickup data provided by Ridwell"


@callback
def async_calculate_quantities(pickups: list[RidwellPickup]) -> dict[str, int]:
    """Calculate the total quanity of pickups in an attr-friendly dict.

    Since Ridwell's API can return distinct pickups for the same category
    (e.g., multiple "Latex Paint" pickups), this is intended to sum them up.
    """
    pickup_types: dict[str, int] = {}

    for pickup in pickups:
        if pickup.category in pickup_types:
            pickup_types[pickup.category] += pickup.quantity
        else:
            pickup_types[pickup.category] = pickup.quantity

    return pickup_types


@callback
def async_get_rotating_category_name(pickups: list[RidwellPickup]) -> str | None:
    """Get the rotating category name from a list of pickups."""
    rotating_category = [pickup.category for pickup in pickups if pickup.rotating]

    if not rotating_category:
        LOGGER.warning("No rotating pickup types found")
        return None

    if len(rotating_category) > 1:
        LOGGER.warning(
            "Multiple candidates for rotating category found (%s); selecting the first",
            rotating_category,
        )

    return rotating_category[0]


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
        next_event = self.coordinator.data[self._account.account_id][0]

        attrs = {
            ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION,
            ATTR_PICKUP_TYPES: async_calculate_quantities(next_event.pickups),
            ATTR_ROTATING_CATEGORY: async_get_rotating_category_name(
                next_event.pickups
            ),
        }

        return attrs

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        next_event = self.coordinator.data[self._account.account_id][0]
        return async_get_utc_midnight(next_event.pickup_date).isoformat()
