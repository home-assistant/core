"""Sensor platform for Garages Amsterdam."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import get_coordinator
from .entity import GaragesAmsterdamEntity

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

    entities: list[GaragesAmsterdamSensor] = []

    for info_type in SENSORS:
        if getattr(coordinator.data[config_entry.data["garage_name"]], info_type) != "":
            entities.append(
                GaragesAmsterdamSensor(
                    coordinator, config_entry.data["garage_name"], info_type
                )
            )

    async_add_entities(entities)


class GaragesAmsterdamSensor(GaragesAmsterdamEntity, SensorEntity):
    """Sensor representing garages amsterdam data."""

    _attr_native_unit_of_measurement = "cars"

    def __init__(
        self, coordinator: DataUpdateCoordinator, garage_name: str, info_type: str
    ) -> None:
        """Initialize garages amsterdam sensor."""
        super().__init__(coordinator, garage_name, info_type)
        self._attr_name = f"{garage_name} - {info_type}".replace("_", " ")
        self._attr_icon = SENSORS[info_type]

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        return self.coordinator.last_update_success and (
            self._garage_name in self.coordinator.data
        )

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return getattr(self.coordinator.data[self._garage_name], self._info_type)
