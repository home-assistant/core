"""Sensor platform for the Kaiterra integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import ATTR_AQI_LEVEL, ATTR_AQI_POLLUTANT
from .coordinator import KaiterraConfigEntry
from .entity import KaiterraEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class KaiterraSensorEntityDescription(SensorEntityDescription):
    """Describe a Kaiterra sensor entity."""

    name: str


SENSORS: tuple[KaiterraSensorEntityDescription, ...] = (
    KaiterraSensorEntityDescription(
        key="aqi",
        name="AQI",
    ),
    KaiterraSensorEntityDescription(
        key="rtemp",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    KaiterraSensorEntityDescription(
        key="rhumid",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    KaiterraSensorEntityDescription(
        key="rpm25c",
        name="PM2.5",
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    KaiterraSensorEntityDescription(
        key="rpm10c",
        name="PM10",
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    KaiterraSensorEntityDescription(
        key="rco2",
        name="CO2",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    KaiterraSensorEntityDescription(
        key="tvoc",
        name="TVOC",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


def _get_state_value(sensor_data: dict[str, Any]) -> StateType:
    """Return a Home Assistant state-compatible value."""
    value = sensor_data.get("value")
    if isinstance(value, str | int | float):
        return value
    return None


async def async_setup_entry(
    hass,
    entry: KaiterraConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kaiterra sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        KaiterraSensor(coordinator, description) for description in SENSORS
    )


class KaiterraSensor(KaiterraEntity, SensorEntity):
    """Representation of a Kaiterra sensor."""

    entity_description: KaiterraSensorEntityDescription

    def __init__(
        self,
        coordinator,
        description: KaiterraSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = description.name
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the current sensor value."""
        return self._sensor.get("value")

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the native unit of measurement."""
        unit = self._sensor.get("unit")
        if not isinstance(unit, str):
            return None

        if self.entity_description.device_class is SensorDeviceClass.TEMPERATURE:
            if unit == "C":
                return UnitOfTemperature.CELSIUS
            if unit == "F":
                return UnitOfTemperature.FAHRENHEIT

        return unit

    @property
    def extra_state_attributes(self) -> dict[str, StateType]:
        """Return extra state attributes for the AQI sensor."""
        if self.entity_description.key != "aqi":
            return {}

        attributes: dict[str, StateType] = {}
        if (aqi_level := self.coordinator.data.get("aqi_level")) and isinstance(
            aqi_level, dict
        ):
            attributes[ATTR_AQI_LEVEL] = _get_state_value(aqi_level)
        if (aqi_pollutant := self.coordinator.data.get("aqi_pollutant")) and isinstance(
            aqi_pollutant, dict
        ):
            attributes[ATTR_AQI_POLLUTANT] = _get_state_value(aqi_pollutant)
        return {key: value for key, value in attributes.items() if value is not None}

    @property
    def _sensor(self) -> dict[str, Any]:
        """Return normalized sensor data for this entity."""
        data = self.coordinator.data.get(self.entity_description.key)
        if isinstance(data, dict):
            return data
        return {}
