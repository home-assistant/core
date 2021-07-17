"""Support for the Forecast.Solar sensor service."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_IDENTIFIERS, ATTR_MANUFACTURER, ATTR_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import ATTR_ENTRY_TYPE, DOMAIN, ENTRY_TYPE_SERVICE, SENSORS
from .models import ForecastSolarSensor


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Defer sensor setup to the shared sensor module."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        ForecastSolarSensorEntity(
            entry_id=entry.entry_id, coordinator=coordinator, sensor=sensor
        )
        for sensor in SENSORS
    )


class ForecastSolarSensorEntity(CoordinatorEntity, SensorEntity):
    """Defines a Forcast.Solar sensor."""

    def __init__(
        self,
        *,
        entry_id: str,
        coordinator: DataUpdateCoordinator,
        sensor: ForecastSolarSensor,
    ) -> None:
        """Initialize Forcast.Solar sensor."""
        super().__init__(coordinator=coordinator)
        self._sensor = sensor

        self.entity_id = f"{SENSOR_DOMAIN}.{sensor.key}"
        self._attr_device_class = sensor.device_class
        self._attr_entity_registry_enabled_default = (
            sensor.entity_registry_enabled_default
        )
        self._attr_name = sensor.name
        self._attr_state_class = sensor.state_class
        self._attr_unique_id = f"{entry_id}_{sensor.key}"
        self._attr_unit_of_measurement = sensor.unit_of_measurement

        self._attr_device_info = {
            ATTR_IDENTIFIERS: {(DOMAIN, entry_id)},
            ATTR_NAME: "Solar Production Forecast",
            ATTR_MANUFACTURER: "Forecast.Solar",
            ATTR_ENTRY_TYPE: ENTRY_TYPE_SERVICE,
        }

    @property
    def state(self) -> StateType:
        """Return the state of the sensor."""
        state: StateType | datetime = getattr(self.coordinator.data, self._sensor.key)
        if isinstance(state, datetime):
            return state.isoformat()
        return state
