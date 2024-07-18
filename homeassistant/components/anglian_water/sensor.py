"""Sensor platform for anglian_water."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AnglianWaterDataUpdateCoordinator
from .entity import AnglianWaterEntity

SENSORS = (
    SensorEntityDescription(
        key="anglian_water_previous_consumption",
        name="Previous Consumption",
        icon="mdi:water",
        native_unit_of_measurement="m³",
        device_class=SensorDeviceClass.WATER,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_devices: AddEntitiesCallback
) -> None:
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_devices(
        AnglianWaterSensor(
            coordinator=coordinator,
            entity_description=sensor,
        )
        for sensor in SENSORS
    )


class AnglianWaterSensor(AnglianWaterEntity, SensorEntity):
    """anglian_water Sensor entity."""

    def __init__(
        self,
        coordinator: AnglianWaterDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__(coordinator, entity_description.key)
        self.entity_description = entity_description

    @property
    def native_value(self) -> float:
        """Return the native value of the sensor."""
        return self.coordinator.client.current_usage
