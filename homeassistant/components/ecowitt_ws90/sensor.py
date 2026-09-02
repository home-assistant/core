"""What the WS90 measures."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from ecowitt_ws90_modbus.sensors import Sensors

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import WS90ConfigEntry
from .entity import WS90Entity, WS90EntityDescription

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class WS90SensorDescription(SensorEntityDescription, WS90EntityDescription):
    """A sensor, and where to read its value off the WS90's readings."""

    value_fn: Callable[[Sensors], StateType]


SENSOR_DESCRIPTIONS: tuple[WS90SensorDescription, ...] = (
    WS90SensorDescription(
        key="light",
        component="sensors",
        translation_key="light",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensors: sensors.light,
    ),
    WS90SensorDescription(
        key="uv_index",
        component="sensors",
        translation_key="uv_index",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensors: sensors.uv_index,
    ),
    WS90SensorDescription(
        key="temperature",
        component="sensors",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensors: sensors.temperature,
    ),
    WS90SensorDescription(
        key="humidity",
        component="sensors",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensors: sensors.humidity,
    ),
    WS90SensorDescription(
        key="wind_speed",
        component="sensors",
        translation_key="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensors: sensors.wind_speed,
    ),
    WS90SensorDescription(
        key="gust_speed",
        component="sensors",
        translation_key="gust_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensors: sensors.gust_speed,
    ),
    WS90SensorDescription(
        key="wind_direction",
        component="sensors",
        translation_key="wind_direction",
        device_class=SensorDeviceClass.WIND_DIRECTION,
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        value_fn=lambda sensors: sensors.wind_direction,
    ),
    WS90SensorDescription(
        key="rainfall",
        component="sensors",
        translation_key="rainfall",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda sensors: sensors.rainfall,
    ),
    WS90SensorDescription(
        key="absolute_pressure",
        component="sensors",
        translation_key="absolute_pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensors: sensors.absolute_pressure,
    ),
    WS90SensorDescription(
        key="rain_counter",
        component="sensors",
        translation_key="rain_counter",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda sensors: sensors.rain_counter,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WS90ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Ecowitt WS90 sensor platform."""
    async_add_entities(
        WS90Sensor(entry.runtime_data, description)
        for description in SENSOR_DESCRIPTIONS
    )


class WS90Sensor(WS90Entity, SensorEntity):
    """A read-only value off the WS90's live sensor readings."""

    entity_description: WS90SensorDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the value this sensor reads from the device."""
        component = getattr(self.coordinator.device, self.entity_description.component)
        return self.entity_description.value_fn(component)
