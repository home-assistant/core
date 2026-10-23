"""Sensor entities for HAVEN IAQ devices."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from haveniaq import ProductType, SensorData

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

from .coordinator import HavenConfigEntry, HavenDataUpdateCoordinator
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

    value_fn: Callable[[SensorData], StateType]
    products: frozenset[ProductType] | None = None


SENSOR_DESCRIPTIONS: tuple[HavenSensorEntityDescription, ...] = (
    HavenSensorEntityDescription(
        key="temperature_c",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        products=AIR_QUALITY_PRODUCTS,
        value_fn=lambda data: data.temperature_c,
    ),
    HavenSensorEntityDescription(
        key="humidity_pct",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        products=AIR_QUALITY_PRODUCTS,
        value_fn=lambda data: data.humidity_pct,
    ),
    HavenSensorEntityDescription(
        key="dew_point_c",
        translation_key="dew_point",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        products=RAM_ONLY,
        value_fn=lambda data: data.dew_point_c,
    ),
    HavenSensorEntityDescription(
        key="pressure_kpa",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        native_unit_of_measurement=UnitOfPressure.KPA,
        state_class=SensorStateClass.MEASUREMENT,
        products=CAM_ONLY,
        value_fn=lambda data: data.pressure_kpa,
    ),
    HavenSensorEntityDescription(
        key="co2_ppm",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        products=AIR_QUALITY_PRODUCTS,
        value_fn=lambda data: data.co2_ppm,
    ),
    HavenSensorEntityDescription(
        key="tvoc_index",
        translation_key="tvoc_index",
        state_class=SensorStateClass.MEASUREMENT,
        products=RAM_ONLY,
        value_fn=lambda data: data.tvoc_index,
    ),
    HavenSensorEntityDescription(
        key="tvoc_ppb",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
        products=CAM_ONLY,
        value_fn=lambda data: data.tvoc_ppb,
    ),
    HavenSensorEntityDescription(
        key="nox_index",
        translation_key="nox_index",
        state_class=SensorStateClass.MEASUREMENT,
        products=RAM_ONLY,
        value_fn=lambda data: data.nox_index,
    ),
    HavenSensorEntityDescription(
        key="pm1_ugm3",
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        products=RAM_ONLY,
        value_fn=lambda data: data.pm1_ugm3,
    ),
    HavenSensorEntityDescription(
        key="pm25_ugm3",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        products=AIR_QUALITY_PRODUCTS,
        value_fn=lambda data: data.pm25_ugm3,
    ),
    HavenSensorEntityDescription(
        key="pm4_ugm3",
        device_class=SensorDeviceClass.PM4,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        products=RAM_ONLY,
        value_fn=lambda data: data.pm4_ugm3,
    ),
    HavenSensorEntityDescription(
        key="pm10_ugm3",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        products=AIR_QUALITY_PRODUCTS,
        value_fn=lambda data: data.pm10_ugm3,
    ),
    HavenSensorEntityDescription(
        key="pm05_count_cm3",
        translation_key="pm05_count",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=CONCENTRATION_PARTICLES_PER_MILLILITER,
        state_class=SensorStateClass.MEASUREMENT,
        products=RAM_ONLY,
        value_fn=lambda data: data.pm05_count_cm3,
    ),
    HavenSensorEntityDescription(
        key="pm1_count_cm3",
        translation_key="pm1_count",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=CONCENTRATION_PARTICLES_PER_MILLILITER,
        state_class=SensorStateClass.MEASUREMENT,
        products=RAM_ONLY,
        value_fn=lambda data: data.pm1_count_cm3,
    ),
    HavenSensorEntityDescription(
        key="pm25_count_cm3",
        translation_key="pm25_count",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=CONCENTRATION_PARTICLES_PER_MILLILITER,
        state_class=SensorStateClass.MEASUREMENT,
        products=AIR_QUALITY_PRODUCTS,
        value_fn=lambda data: data.pm25_count_cm3,
    ),
    HavenSensorEntityDescription(
        key="pm4_count_cm3",
        translation_key="pm4_count",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=CONCENTRATION_PARTICLES_PER_MILLILITER,
        state_class=SensorStateClass.MEASUREMENT,
        products=RAM_ONLY,
        value_fn=lambda data: data.pm4_count_cm3,
    ),
    HavenSensorEntityDescription(
        key="pm10_count_cm3",
        translation_key="pm10_count",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=CONCENTRATION_PARTICLES_PER_MILLILITER,
        state_class=SensorStateClass.MEASUREMENT,
        products=AIR_QUALITY_PRODUCTS,
        value_fn=lambda data: data.pm10_count_cm3,
    ),
    HavenSensorEntityDescription(
        key="airflow_mps",
        translation_key="airflow",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        products=CAM_ONLY,
        value_fn=lambda data: data.airflow_mps,
    ),
    HavenSensorEntityDescription(
        key="airflow_duration_s",
        translation_key="airflow_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        products=CAM_ONLY,
        value_fn=lambda data: data.airflow_duration_s,
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
        return super().available and self.coordinator.data.sensor_ready
