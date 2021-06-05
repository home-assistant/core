"""Support for the Forecast Solar sensor service."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_NAME, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, SENSORS


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Defer sensor setup to the shared sensor module."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        ForecastSolarSensor(entry=entry, coordinator=coordinator, key=key)
        for key in SENSORS
    )


class ForecastSolarSensor(CoordinatorEntity, SensorEntity):
    """Defines a Forcast.Solar sensor."""

    def __init__(
        self, entry: ConfigEntry, coordinator: DataUpdateCoordinator, key: str
    ) -> None:
        """Initialize Forcast.Solar sensor."""
        super().__init__(coordinator=coordinator)
        self._attr_name = SENSORS[key][ATTR_NAME]
        self._attr_unit_of_measurement = SENSORS[key][ATTR_UNIT_OF_MEASUREMENT]
        self._attr_device_class = SENSORS[key][ATTR_DEVICE_CLASS]
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._key = key

    @property
    def state(self) -> float:
        """Return the state of the sensor."""
        return getattr(self.coordinator.data, self._key)
