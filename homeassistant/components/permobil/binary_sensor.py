"""Platform for binary sensor integration."""
from __future__ import annotations

import logging

from mypermobil import BATTERY_CHARGING

from homeassistant import config_entries
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MyPermobilCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create and setup the binary sensor."""

    coordinator: MyPermobilCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities((IsChargingSensor(coordinator=coordinator),))


class IsChargingSensor(CoordinatorEntity[MyPermobilCoordinator], BinarySensorEntity):
    """Representation of a Binary Sensor.

    Binary sensor that returns whether the wheelchair is charging or not
    """

    def __init__(
        self,
        coordinator: MyPermobilCoordinator,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = f"{coordinator.p_api.email}_is_charging"

    @property
    def is_on(self) -> bool:
        """Return True if the wheelchair is charging."""
        return bool(self.coordinator.data.battery[BATTERY_CHARGING[0]])

    @property
    def available(self) -> bool:
        """Return True if the sensor has value."""
        return (
            super().available and BATTERY_CHARGING[0] in self.coordinator.data.battery
        )
