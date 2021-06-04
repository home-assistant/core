"""Support for the Forecast Solar sensor service."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import get_coordinator

SENSORS = {
    "watts": "mdi:sun",
    "watt_hours": "mdi:sun",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Defer sensor setup to the shared sensor module."""
    coordinator = await get_coordinator(hass, entry)

    entities: list[ForecastSolarSensor] = []

    for info_type in SENSORS:
        entities.append(ForecastSolarSensor(coordinator, entry.data["name"], info_type))

    async_add_entities(entities)


class ForecastSolarSensor(CoordinatorEntity, SensorEntity):
    """Define an Forecast Solar sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, name: str, info_type: str
    ) -> None:
        """Initialize forecast solar sensor."""
        super().__init__(coordinator)
        self._unique_id = f"{name}-{info_type}"
        self._name = name
        self._info_type = info_type
        self._name = f"{name} - {info_type}"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique id of the device."""
        return self._unique_id

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return getattr(self.coordinator.data[self._name], self._info_type)

    @property
    def unit_of_measurement(self) -> str:
        """Return unit of measurement."""
        return "Watt"
