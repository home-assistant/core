"""Support for the Nettigo Air Monitor service."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from nettigo_air_monitor import NAMSensors

from homeassistant.components.sensor import (
    DOMAIN as PLATFORM,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import utcnow

from . import NAMDataUpdateCoordinator
from .const import (
    ATTR_BME280_HUMIDITY,
    ATTR_BME280_PRESSURE,
    ATTR_BME280_TEMPERATURE,
    ATTR_BMP180_PRESSURE,
    ATTR_BMP180_TEMPERATURE,
    ATTR_BMP280_PRESSURE,
    ATTR_BMP280_TEMPERATURE,
    ATTR_DHT22_HUMIDITY,
    ATTR_DHT22_TEMPERATURE,
    ATTR_HECA_HUMIDITY,
    ATTR_HECA_TEMPERATURE,
    ATTR_MHZ14A_CARBON_DIOXIDE,
    ATTR_PMSX003_CAQI,
    ATTR_PMSX003_CAQI_LEVEL,
    ATTR_PMSX003_P0,
    ATTR_PMSX003_P1,
    ATTR_PMSX003_P2,
    ATTR_SDS011_CAQI,
    ATTR_SDS011_CAQI_LEVEL,
    ATTR_SDS011_P1,
    ATTR_SDS011_P2,
    ATTR_SHT3X_HUMIDITY,
    ATTR_SHT3X_TEMPERATURE,
    ATTR_SIGNAL_STRENGTH,
    ATTR_SPS30_CAQI,
    ATTR_SPS30_CAQI_LEVEL,
    ATTR_SPS30_P0,
    ATTR_SPS30_P1,
    ATTR_SPS30_P2,
    ATTR_SPS30_P4,
    ATTR_UPTIME,
    DOMAIN,
    MIGRATION_SENSORS,
)

PARALLEL_UPDATES = 1

_LOGGER = logging.getLogger(__name__)


@dataclass
class NAMSensorRequiredKeysMixin:
    """Class for NAM entity required keys."""

    value: Callable[[NAMSensors], StateType | datetime]


@dataclass
class NAMSensorEntityDescription(SensorEntityDescription, NAMSensorRequiredKeysMixin):
    """NAM sensor entity description."""


SENSORS: tuple[NAMSensorEntityDescription, ...] = (
    NAMSensorEntityDescription(
        key=ATTR_BME280_HUMIDITY,
        translation_key="bme280_humidity",
        suggested_display_precision=1,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda sensors: sensors.bme280_humidity,
    ),
    NAMSensorEntityDescription(
        key=ATTR_BME280_PRESSURE,
        translation_key="bme280_pressure",
        suggested_display_precision=0,
        native_unit_of_measurement=UnitOfPressure.HPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda sensors: sensors.bme280_pressure,
    ),
    NAMSensorEntityDescription(
        key=ATTR_BME280_TEMPERATURE,
        translation_key="bme280_temperature",
        suggested_display_precision=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda sensors: sensors.bme280_temperature,
    ),
    NAMSensorEntityDescription(
        key=ATTR_BMP180_PRESSURE,
        translation_key="bmp180_pressure",
        suggested_display_precision=0,
        native_unit_of_measurement=UnitOfPressure.HPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda sensors: sensors.bmp180_pressure,
    ),
    NAMSensorEntityDescription(
        key=ATTR_BMP180_TEMPERATURE,
        translation_key="bmp180_temperature",
        suggested_display_precision=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda sensors: sensors.bmp180_temperature,
    ),
    NAMSensorEntityDescription(
        key=ATTR_BMP280_PRESSURE,
        translation_key="bmp280_pressure",
        suggested_display_precision=0,
        native_unit_of_measurement=UnitOfPressure.HPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda sensors: sensors.bmp280_pressure,
    ),
    NAMSensorEntityDescription(
        key=ATTR_BMP280_TEMPERATURE,
        translation_key="bmp280_temperature",
        suggested_display_precision=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda sensors: sensors.bmp280_temperature,
    ),
    NAMSensorEntityDescription(
        key=ATTR_HECA_HUMIDITY,
        translation_key="heca_humidity",
        suggested_display_precision=1,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda sensors: sensors.heca_humidity,
    ),
    NAMSensorEntityDescription(
        key=ATTR_HECA_TEMPERATURE,
        translation_key="heca_temperature",
        suggested_display_precision=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda sensors: sensors.heca_temperature,
    ),
    NAMSensorEntityDescription(
        key=ATTR_MHZ14A_CARBON_DIOXIDE,
        translation_key="mhz14a_carbon_dioxide",
        suggested_display_precision=0,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda sensors: sensors.mhz14a_carbon_dioxide,
    ),
    NAMSensorEntityDescription(
        key=ATTR_PMSX003_CAQI,
        translation_key="pmsx003_caqi",
        icon="mdi:air-filter",
        value=lambda sensors: sensors.pms_caqi,
    ),
    NAMSensorEntityDescription(
        key=ATTR_PMSX003_CAQI_LEVEL,
        translation_key="pmsx003_caqi_level",
        icon="mdi:air-filter",
        device_class=SensorDeviceClass.ENUM,
        options=["very_low", "low", "medium", "high", "very_high"],
        value=lambda sensors: sensors.pms_caqi_level,
    ),
    NAMSensorEntityDescription(
        key=ATTR_PMSX003_P0,
        translation_key="pmsx003_pm1",
        suggested_display_precision=0,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM1,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda sensors: sensors.pms_p0,
    ),
    NAMSensorEntityDescription(
        key=ATTR_PMSX003_P1,
        translation_key="pmsx003_pm10",
        suggested_display_precision=0,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda sensors: sensors.pms_p1,
    ),
    NAMSensorEntityDescription(
        key=ATTR_PMSX003_P2,
        translation_key="pmsx003_pm25",
        suggested_display_precision=0,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda sensors: sensors.pms_p2,
    ),
    NAMSensorEntityDescription(
        key=ATTR_SDS011_CAQI,
        translation_key="sds011_caqi",
        icon="mdi:air-filter",
        value=lambda sensors: sensors.sds011_caqi,
    ),
    NAMSensorEntityDescription(
        key=ATTR_SDS011_CAQI_LEVEL,
        translation_key="sds011_caqi_level",
        icon="mdi:air-filter",
        device_class=SensorDeviceClass.ENUM,
        options=["very_low", "low", "medium", "high", "very_high"],
        value=lambda sensors: sensors.sds011_caqi_level,
    ),
    NAMSensorEntityDescription(
        key=ATTR_SDS011_P1,
        translation_key="sds011_pm10",
        suggested_display_precision=0,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda sensors: sensors.sds011_p1,
    ),
    NAMSensorEntityDescription(
        key=ATTR_SDS011_P2,
        translation_key="sds011_pm25",
        suggested_display_precision=0,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda sensors: sensors.sds011_p2,
    ),
    NAMSensorEntityDescription(
        key=ATTR_SHT3X_HUMIDITY,
        translation_key="sht3x_humidity",
        suggested_display_precision=1,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda sensors: sensors.sht3x_humidity,
    ),
    NAMSensorEntityDescription(
        key=ATTR_SHT3X_TEMPERATURE,
        translation_key="sht3x_temperature",
        suggested_display_precision=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda sensors: sensors.sht3x_temperature,
    ),
    NAMSensorEntityDescription(
        key=ATTR_SPS30_CAQI,
        translation_key="sps30_caqi",
        icon="mdi:air-filter",
        value=lambda sensors: sensors.sps30_caqi,
    ),
    NAMSensorEntityDescription(
        key=ATTR_SPS30_CAQI_LEVEL,
        translation_key="sps30_caqi_level",
        icon="mdi:air-filter",
        device_class=SensorDeviceClass.ENUM,
        options=["very_low", "low", "medium", "high", "very_high"],
        value=lambda sensors: sensors.sps30_caqi_level,
    ),
    NAMSensorEntityDescription(
        key=ATTR_SPS30_P0,
        translation_key="sps30_pm1",
        suggested_display_precision=0,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM1,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda sensors: sensors.sps30_p0,
    ),
    NAMSensorEntityDescription(
        key=ATTR_SPS30_P1,
        translation_key="sps30_pm10",
        suggested_display_precision=0,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda sensors: sensors.sps30_p1,
    ),
    NAMSensorEntityDescription(
        key=ATTR_SPS30_P2,
        translation_key="sps30_pm25",
        suggested_display_precision=0,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda sensors: sensors.sps30_p2,
    ),
    NAMSensorEntityDescription(
        key=ATTR_SPS30_P4,
        translation_key="sps30_pm4",
        suggested_display_precision=0,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        icon="mdi:molecule",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda sensors: sensors.sps30_p4,
    ),
    NAMSensorEntityDescription(
        key=ATTR_DHT22_HUMIDITY,
        translation_key="dht22_humidity",
        suggested_display_precision=1,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda sensors: sensors.dht22_humidity,
    ),
    NAMSensorEntityDescription(
        key=ATTR_DHT22_TEMPERATURE,
        translation_key="dht22_temperature",
        suggested_display_precision=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda sensors: sensors.dht22_temperature,
    ),
    NAMSensorEntityDescription(
        key=ATTR_SIGNAL_STRENGTH,
        suggested_display_precision=0,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda sensors: sensors.signal,
    ),
    NAMSensorEntityDescription(
        key=ATTR_UPTIME,
        translation_key="last_restart",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda sensors: utcnow() - timedelta(seconds=sensors.uptime or 0),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add a Nettigo Air Monitor entities from a config_entry."""
    coordinator: NAMDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Due to the change of the attribute name of two sensors, it is necessary to migrate
    # the unique_ids to the new names.
    ent_reg = er.async_get(hass)
    for old_sensor, new_sensor in MIGRATION_SENSORS:
        old_unique_id = f"{coordinator.unique_id}-{old_sensor}"
        new_unique_id = f"{coordinator.unique_id}-{new_sensor}"
        if entity_id := ent_reg.async_get_entity_id(PLATFORM, DOMAIN, old_unique_id):
            _LOGGER.debug(
                "Migrating entity %s from old unique ID '%s' to new unique ID '%s'",
                entity_id,
                old_unique_id,
                new_unique_id,
            )
            ent_reg.async_update_entity(entity_id, new_unique_id=new_unique_id)

    sensors: list[NAMSensor] = []
    for description in SENSORS:
        if getattr(coordinator.data, description.key) is not None:
            sensors.append(NAMSensor(coordinator, description))

    async_add_entities(sensors, False)


class NAMSensor(CoordinatorEntity[NAMDataUpdateCoordinator], SensorEntity):
    """Define an Nettigo Air Monitor sensor."""

    _attr_has_entity_name = True
    entity_description: NAMSensorEntityDescription

    def __init__(
        self,
        coordinator: NAMDataUpdateCoordinator,
        description: NAMSensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.unique_id}-{description.key}"
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        available = super().available

        # For a short time after booting, the device does not return values for all
        # sensors. For this reason, we mark entities for which data is missing as
        # unavailable.
        return (
            available
            and getattr(self.coordinator.data, self.entity_description.key) is not None
        )

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state."""
        return self.entity_description.value(self.coordinator.data)
