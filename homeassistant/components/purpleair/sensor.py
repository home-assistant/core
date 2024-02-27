"""Support for PurpleAir sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from aiopurpleair.models.sensors import SensorModel

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PurpleAirEntity
from .const import CONF_SENSOR_INDICES, DOMAIN
from .coordinator import PurpleAirDataUpdateCoordinator

CONCENTRATION_PARTICLES_PER_100_MILLILITERS = f"particles/100{UnitOfVolume.MILLILITERS}"


@dataclass(frozen=True, kw_only=True)
class PurpleAirSensorEntityDescription(SensorEntityDescription):
    """Define an object to describe PurpleAir sensor entities."""

    value_fn: Callable[[SensorModel], float | str | None]


SENSOR_DESCRIPTIONS = [
    PurpleAirSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.humidity,
    ),
    PurpleAirSensorEntityDescription(
        key="pm0.3_count_concentration",
        translation_key="pm0_3_count_concentration",
        entity_registry_enabled_default=False,
        icon="mdi:blur",
        native_unit_of_measurement=CONCENTRATION_PARTICLES_PER_100_MILLILITERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pm0_3_um_count,
    ),
    PurpleAirSensorEntityDescription(
        key="pm0.5_count_concentration",
        translation_key="pm0_5_count_concentration",
        entity_registry_enabled_default=False,
        icon="mdi:blur",
        native_unit_of_measurement=CONCENTRATION_PARTICLES_PER_100_MILLILITERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pm0_5_um_count,
    ),
    PurpleAirSensorEntityDescription(
        key="pm1.0_count_concentration",
        translation_key="pm1_0_count_concentration",
        entity_registry_enabled_default=False,
        icon="mdi:blur",
        native_unit_of_measurement=CONCENTRATION_PARTICLES_PER_100_MILLILITERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pm1_0_um_count,
    ),
    PurpleAirSensorEntityDescription(
        key="pm1.0_mass_concentration",
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pm1_0,
    ),
    PurpleAirSensorEntityDescription(
        key="pm10.0_count_concentration",
        translation_key="pm10_0_count_concentration",
        entity_registry_enabled_default=False,
        icon="mdi:blur",
        native_unit_of_measurement=CONCENTRATION_PARTICLES_PER_100_MILLILITERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pm10_0_um_count,
    ),
    PurpleAirSensorEntityDescription(
        key="pm10.0_mass_concentration",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pm10_0,
    ),
    PurpleAirSensorEntityDescription(
        key="pm2.5_count_concentration",
        translation_key="pm2_5_count_concentration",
        entity_registry_enabled_default=False,
        icon="mdi:blur",
        native_unit_of_measurement=CONCENTRATION_PARTICLES_PER_100_MILLILITERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pm2_5_um_count,
    ),
    PurpleAirSensorEntityDescription(
        key="pm2.5_mass_concentration",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pm2_5,
    ),
    PurpleAirSensorEntityDescription(
        key="pm5.0_count_concentration",
        translation_key="pm5_0_count_concentration",
        entity_registry_enabled_default=False,
        icon="mdi:blur",
        native_unit_of_measurement=CONCENTRATION_PARTICLES_PER_100_MILLILITERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pm5_0_um_count,
    ),
    PurpleAirSensorEntityDescription(
        key="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pressure,
    ),
    PurpleAirSensorEntityDescription(
        key="rssi",
        translation_key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pressure,
    ),
    PurpleAirSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.temperature,
    ),
    PurpleAirSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda sensor: sensor.uptime,
    ),
    PurpleAirSensorEntityDescription(
        # This sensor is an air quality index for VOCs. More info at https://github.com/home-assistant/core/pull/84896
        key="voc",
        translation_key="voc_aqi",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.voc,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PurpleAir sensors based on a config entry."""
    coordinator: PurpleAirDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        PurpleAirSensorEntity(coordinator, entry, sensor_index, description)
        for sensor_index in entry.options[CONF_SENSOR_INDICES]
        for description in SENSOR_DESCRIPTIONS
    )


class PurpleAirSensorEntity(PurpleAirEntity, SensorEntity):
    """Define a representation of a PurpleAir sensor."""

    entity_description: PurpleAirSensorEntityDescription

    def __init__(
        self,
        coordinator: PurpleAirDataUpdateCoordinator,
        entry: ConfigEntry,
        sensor_index: int,
        description: PurpleAirSensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, sensor_index)

        self._attr_unique_id = f"{self._sensor_index}-{description.key}"
        self.entity_description = description

    @property
    def native_value(self) -> float | str | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.sensor_data)
