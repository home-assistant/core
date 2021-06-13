"""Sensor platform for Garages Amsterdam."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import get_coordinator
from .const import ATTRIBUTION

SENSORS = {
    "free_space_short": "mdi:car",
    "free_space_long": "mdi:car",
    "short_capacity": "mdi:car",
    "long_capacity": "mdi:car",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Defer sensor setup to the shared sensor module."""
    coordinator = await get_coordinator(hass)

    entities: list[GaragesamsterdamSensor] = []

    for info_type in SENSORS:
        if getattr(coordinator.data[config_entry.data["garage_name"]], info_type) != "":
            entities.append(
                GaragesamsterdamSensor(
                    coordinator, config_entry.data["garage_name"], info_type
                )
            )

    async_add_entities(entities)


class GaragesamsterdamSensor(CoordinatorEntity, SensorEntity):
    """Sensor representing garages amsterdam data."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, garage_name: str, info_type: str
    ) -> None:
        """Initialize garages amsterdam sensor."""
        super().__init__(coordinator)
        self._unique_id = f"{garage_name}-{info_type}"
        self._garage_name = garage_name
        self._info_type = info_type
        self._name = f"{garage_name} - {info_type}".replace("_", " ")

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique id of the device."""
        return self._unique_id

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        return self.coordinator.last_update_success and (
            self._garage_name in self.coordinator.data
        )

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return getattr(self.coordinator.data[self._garage_name], self._info_type)

    @property
    def icon(self) -> str:
        """Return the icon."""
        return SENSORS[self._info_type]

    @property
    def unit_of_measurement(self) -> str:
        """Return unit of measurement."""
        return "cars"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device attributes."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}
