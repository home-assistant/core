"""Support for Ridwell sensors."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from aioridwell.model import RidwellAccount

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SENSOR_TYPE_NEXT_PICKUP
from .coordinator import RidwellDataUpdateCoordinator
from .entity import RidwellEntity

ATTR_CATEGORY = "category"
ATTR_PICKUP_STATE = "pickup_state"
ATTR_PICKUP_TYPES = "pickup_types"
ATTR_QUANTITY = "quantity"

SENSOR_DESCRIPTION = SensorEntityDescription(
    key=SENSOR_TYPE_NEXT_PICKUP,
    name="Ridwell pickup",
    device_class=SensorDeviceClass.DATE,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Ridwell sensors based on a config entry."""
    coordinator: RidwellDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        RidwellSensor(coordinator, account, SENSOR_DESCRIPTION)
        for account in coordinator.accounts.values()
    )


class RidwellSensor(RidwellEntity, SensorEntity):
    """Define a Ridwell pickup sensor."""

    def __init__(
        self,
        coordinator: RidwellDataUpdateCoordinator,
        account: RidwellAccount,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, account, description)

        self._attr_name = f"{description.name} ({account.address['street1']})"

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return entity specific state attributes."""
        attrs: dict[str, Any] = {
            ATTR_PICKUP_TYPES: {},
            ATTR_PICKUP_STATE: self.next_pickup_event.state.value,
        }

        for pickup in self.next_pickup_event.pickups:
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
    def native_value(self) -> date:
        """Return the value reported by the sensor."""
        return self.next_pickup_event.pickup_date
