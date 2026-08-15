"""Sensor entities for HAVEN IAQ devices."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from haveniaq import ProductType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfDensity,
    UnitOfPressure,
    UnitOfRatio,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import (
    HavenConfigEntry,
    HavenCoordinatorData,
    HavenDataUpdateCoordinator,
)
from .entity import HavenEntity

CONCENTRATION_PARTICLES_PER_MILLILITER = f"particles/{UnitOfVolume.MILLILITERS}"
AIR_QUALITY_PRODUCTS = frozenset(
    {ProductType.ROOM_AIR_MONITOR, ProductType.CENTRAL_AIR_MONITOR}
)
RAM_ONLY = frozenset({ProductType.ROOM_AIR_MONITOR})
CAM_ONLY = frozenset({ProductType.CENTRAL_AIR_MONITOR})

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class HavenSensorEntityDescription(SensorEntityDescription):
    """Describe a HAVEN sensor."""

    value_fn: Callable[[HavenCoordinatorData], StateType]
    products: frozenset[ProductType] | None = None


SENSOR_DESCRIPTIONS: tuple[HavenSensorEntityDescription, ...] = (
    HavenSensorEntityDescription(
        key="temperature_c",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        products=AIR_QUALITY_PRODUCTS,
        value_fn=lambda data: data.sensors.temperature_c,
    ),
    HavenSensorEntityDescription(
        key="humidity_pct",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        products=AIR_QUALITY_PRODUCTS,
        value_fn=lambda data: data.sensors.humidity_pct,
    ),
    HavenSensorEntityDescription(
        key="dew_point_c",
        translation_key="dew_point",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        products=RAM_ONLY,
        value_fn=lambda data: data.sensors.dew_point_c,
    ),
    HavenSensorEntityDescription(
        key="pressure_kpa",
        translation_key="pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        native_unit_of_measurement=UnitOfPressure.KPA,
        state_class=SensorStateClass.MEASUREMENT,
        products=CAM_ONLY,
        value_fn=lambda data: data.sensors.pressure_kpa,
    ),
    HavenSensorEntityDescription(
        key="co2_ppm",
        translation_key="carbon_dioxide",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        products=AIR_QUALITY_PRODUCTS,
        value_fn=lambda data: data.sensors.co2_ppm,
    ),
    HavenSensorEntityDescription(
        key="tvoc_index",
        translation_key="tvoc_index",
        state_class=SensorStateClass.MEASUREMENT,
        products=RAM_ONLY,
        value_fn=lambda data: data.sensors.tvoc_index,
    ),
    HavenSensorEntityDescription(
        key="tvoc_ppb",
        translation_key="tvoc",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
        products=CAM_ONLY,
        value_fn=lambda data: data.sensors.tvoc_ppb,
    ),
    HavenSensorEntityDescription(
        key="nox_index",
        translation_key="nox_index",
        state_class=SensorStateClass.MEASUREMENT,
        products=RAM_ONLY,
        value_fn=lambda data: data.sensors.nox_index,
    ),
    HavenSensorEntityDescription(
        key="pm1_ugm3",
        translation_key="pm1_mass",
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        products=RAM_ONLY,
        value_fn=lambda data: data.sensors.pm1_ugm3,
    ),
    HavenSensorEntityDescription(
        key="pm25_ugm3",
        translation_key="pm25_mass",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        products=AIR_QUALITY_PRODUCTS,
        value_fn=lambda data: data.sensors.pm25_ugm3,
    ),
    HavenSensorEntityDescription(
        key="pm4_ugm3",
        translation_key="pm4_mass",
        device_class=SensorDeviceClass.PM4,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        products=RAM_ONLY,
        value_fn=lambda data: data.sensors.pm4_ugm3,
    ),
    HavenSensorEntityDescription(
        key="pm10_ugm3",
        translation_key="pm10_mass",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        products=AIR_QUALITY_PRODUCTS,
        value_fn=lambda data: data.sensors.pm10_ugm3,
    ),
    HavenSensorEntityDescription(
        key="pm05_count_cm3",
        translation_key="pm05_count",
        native_unit_of_measurement=CONCENTRATION_PARTICLES_PER_MILLILITER,
        state_class=SensorStateClass.MEASUREMENT,
        products=RAM_ONLY,
        value_fn=lambda data: data.sensors.pm05_count_cm3,
    ),
    HavenSensorEntityDescription(
        key="pm1_count_cm3",
        translation_key="pm1_count",
        native_unit_of_measurement=CONCENTRATION_PARTICLES_PER_MILLILITER,
        state_class=SensorStateClass.MEASUREMENT,
        products=RAM_ONLY,
        value_fn=lambda data: data.sensors.pm1_count_cm3,
    ),
    HavenSensorEntityDescription(
        key="pm25_count_cm3",
        translation_key="pm25_count",
        native_unit_of_measurement=CONCENTRATION_PARTICLES_PER_MILLILITER,
        state_class=SensorStateClass.MEASUREMENT,
        products=AIR_QUALITY_PRODUCTS,
        value_fn=lambda data: data.sensors.pm25_count_cm3,
    ),
    HavenSensorEntityDescription(
        key="pm4_count_cm3",
        translation_key="pm4_count",
        native_unit_of_measurement=CONCENTRATION_PARTICLES_PER_MILLILITER,
        state_class=SensorStateClass.MEASUREMENT,
        products=RAM_ONLY,
        value_fn=lambda data: data.sensors.pm4_count_cm3,
    ),
    HavenSensorEntityDescription(
        key="pm10_count_cm3",
        translation_key="pm10_count",
        native_unit_of_measurement=CONCENTRATION_PARTICLES_PER_MILLILITER,
        state_class=SensorStateClass.MEASUREMENT,
        products=AIR_QUALITY_PRODUCTS,
        value_fn=lambda data: data.sensors.pm10_count_cm3,
    ),
    HavenSensorEntityDescription(
        key="airflow_mps",
        translation_key="airflow",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        products=CAM_ONLY,
        value_fn=lambda data: data.sensors.airflow_mps,
    ),
    HavenSensorEntityDescription(
        key="airflow_duration_s",
        translation_key="airflow_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        products=CAM_ONLY,
        value_fn=lambda data: data.sensors.airflow_duration_s,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HavenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors supported by a HAVEN product."""
    coordinator = entry.runtime_data
    product_type = coordinator.info.product_type
    async_add_entities(
        HavenSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
        if description.products is None or product_type in description.products
    )


class HavenSensor(HavenEntity, SensorEntity):
    """Represent a HAVEN sensor."""

    entity_description: HavenSensorEntityDescription

    def __init__(
        self,
        coordinator: HavenDataUpdateCoordinator,
        description: HavenSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.info.serial_number}_{description.key}"

    @property
    @override
    def native_value(self) -> StateType:
        """Return the current sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    @override
    def available(self) -> bool:
        """Return whether the entity has current data."""
        return super().available and self.coordinator.data.sensors.sensor_ready
