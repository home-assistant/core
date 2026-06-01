"""Support for openSenseMap sensors."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_STATION_ID, DOMAIN, INTEGRATION_TITLE
from .coordinator import (
    Measurement,
    OpenSenseMapConfigEntry,
    OpenSenseMapCoordinator,
    OpenSenseMapStationData,
)


@dataclass(frozen=True, kw_only=True)
class OpenSenseMapSensorEntityDescription(SensorEntityDescription):
    """Describes openSenseMap sensor entities."""

    value_fn: Callable[[OpenSenseMapStationData], Measurement]


SENSOR_DESCRIPTIONS: tuple[OpenSenseMapSensorEntityDescription, ...] = (
    OpenSenseMapSensorEntityDescription(
        key="pm2_5",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.pm2_5,
    ),
    OpenSenseMapSensorEntityDescription(
        key="pm10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.pm10,
    ),
    OpenSenseMapSensorEntityDescription(
        key="pm1_0",
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.pm1_0,
    ),
    OpenSenseMapSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.temperature,
    ),
    OpenSenseMapSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.humidity,
    ),
    OpenSenseMapSensorEntityDescription(
        key="air_pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.air_pressure,
    ),
    OpenSenseMapSensorEntityDescription(
        key="illuminance",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.illuminance,
    ),
    OpenSenseMapSensorEntityDescription(
        key="uv_index",
        translation_key="uv_index",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.uv,
    ),
    OpenSenseMapSensorEntityDescription(
        key="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.wind_speed,
    ),
    OpenSenseMapSensorEntityDescription(
        key="wind_direction",
        device_class=SensorDeviceClass.WIND_DIRECTION,
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        value_fn=lambda data: data.wind_direction,
    ),
    OpenSenseMapSensorEntityDescription(
        key="precipitation",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.precipitation,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenSenseMapConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up openSenseMap sensors from a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data
    entities: list[OpenSenseMapSensor] = []
    for description in SENSOR_DESCRIPTIONS:
        measurement = description.value_fn(data)
        if measurement.value is None:
            continue
        native_unit = measurement.unit or description.native_unit_of_measurement
        entities.append(OpenSenseMapSensor(coordinator, description, native_unit))
    async_add_entities(entities)


class OpenSenseMapSensor(CoordinatorEntity[OpenSenseMapCoordinator], SensorEntity):
    """Sensor entity representing a single measurement from an openSenseMap station."""

    _attr_attribution = "Data provided by openSenseMap"
    _attr_has_entity_name = True
    entity_description: OpenSenseMapSensorEntityDescription

    def __init__(
        self,
        coordinator: OpenSenseMapCoordinator,
        description: OpenSenseMapSensorEntityDescription,
        native_unit: str | None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_native_unit_of_measurement = native_unit
        station_id = coordinator.config_entry.data[CONF_STATION_ID]
        self._attr_unique_id = f"{station_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, station_id)},
            manufacturer=INTEGRATION_TITLE,
            configuration_url=f"https://opensensemap.org/explore/{station_id}",
        )

    @property
    def native_value(self) -> float | str | None:
        """Return the latest value reported by the station."""
        return self.entity_description.value_fn(self.coordinator.data).value
