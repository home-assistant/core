"""Support for Ridwell sensors."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from aioridwell.model import RidwellAccount, RidwellPickupEvent

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import RidwellEntity
from .const import DATA_ACCOUNT, DATA_COORDINATOR, DOMAIN, SENSOR_TYPE_NEXT_PICKUP

ATTR_CATEGORY = "category"
ATTR_PICKUP_STATE = "pickup_state"
ATTR_PICKUP_TYPES = "pickup_types"
ATTR_QUANTITY = "quantity"

SENSOR_DESCRIPTION = SensorEntityDescription(
    key=SENSOR_TYPE_NEXT_PICKUP,
    name="Ridwell Pickup",
    device_class=SensorDeviceClass.DATE,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Ridwell sensors based on a config entry."""
    accounts = hass.data[DOMAIN][entry.entry_id][DATA_ACCOUNT]
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    async_add_entities(
        [
            RidwellSensor(coordinator, account, SENSOR_DESCRIPTION)
            for account in accounts.values()
        ]
    )


class RidwellSensor(RidwellEntity, SensorEntity):
    """Define a Ridwell pickup sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        account: RidwellAccount,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, account, description)

        self._attr_name = f"{description.name} ({account.address['street1']})"

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return entity specific state attributes."""
        event = self.coordinator.data[self._account.account_id]

        attrs: dict[str, Any] = {
            ATTR_PICKUP_TYPES: {},
            ATTR_PICKUP_STATE: event.state.value,
        }

        for pickup in event.pickups:
            if pickup.name not in attrs[ATTR_PICKUP_TYPES]:
                attrs[ATTR_PICKUP_TYPES][pickup.name] = {
                    ATTR_CATEGORY: pickup.category.value,
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
