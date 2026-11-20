"""Support for IRM KMI sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_UNIQUE_ID,
    DEGREE,
    UV_INDEX,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import IrmKmiConfigEntry
from .data import ProcessedCoordinatorData
from .entity import IrmKmiBaseEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class IrmKmiSensorEntityDescription(SensorEntityDescription):
    """Class describing IRM KMI sensor entities."""

    value_fn: Callable[[ProcessedCoordinatorData], StateType]


SENSOR_TYPES: tuple[IrmKmiSensorEntityDescription, ...] = (
    IrmKmiSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: data.current_weather.get("temperature"),
    ),
    IrmKmiSensorEntityDescription(
        key="pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.HPA,
        value_fn=lambda data: data.current_weather.get("pressure"),
    ),
    IrmKmiSensorEntityDescription(
        key="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda data: data.current_weather.get("wind_speed"),
    ),
    IrmKmiSensorEntityDescription(
        key="wind_gust_speed",
        translation_key="wind_gust_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.current_weather.get("wind_gust_speed"),
    ),
    IrmKmiSensorEntityDescription(
        key="wind_bearing",
        device_class=SensorDeviceClass.WIND_DIRECTION,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        native_unit_of_measurement=DEGREE,
        value_fn=lambda data: data.current_weather.get("wind_bearing"),
    ),
    IrmKmiSensorEntityDescription(
        key="uv_index",
        translation_key="uv_index",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UV_INDEX,
        value_fn=lambda data: data.current_weather.get("uv_index"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IrmKmiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    async_add_entities(IrmKmiSensor(entry, description) for description in SENSOR_TYPES)


class IrmKmiSensor(IrmKmiBaseEntity, SensorEntity):
    """Sensor for a value reported by IRM KMI."""

    entity_description: IrmKmiSensorEntityDescription

    def __init__(
        self,
        entry: IrmKmiConfigEntry,
        description: IrmKmiSensorEntityDescription,
    ) -> None:
        """Create a new instance of the sensor from a configuration entry."""
        super().__init__(entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.data[CONF_UNIQUE_ID]}-{description.key}"

    @property
    @override
    def native_value(self) -> StateType:
        """Return the current value of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
