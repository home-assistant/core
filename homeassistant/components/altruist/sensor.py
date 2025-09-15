"""Defines the Altruist sensor platform."""

from collections.abc import Callable
from dataclasses import dataclass
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfPressure,
    UnitOfSoundPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AltruistConfigEntry
from .coordinator import AltruistDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class AltruistSensorEntityDescription(SensorEntityDescription):
    """Class to describe a Sensor entity."""

    native_value_fn: Callable[[str], float] = float
    state_class = SensorStateClass.MEASUREMENT


SENSOR_DESCRIPTIONS = [
    AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.HUMIDITY,
        key="BME280_humidity",
        translation_key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=2,
        translation_placeholders={"sensor_name": "BME280"},
    ),
    AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.PRESSURE,
        key="BME280_pressure",
        translation_key="pressure",
        native_unit_of_measurement=UnitOfPressure.PA,
        suggested_unit_of_measurement=UnitOfPressure.MMHG,
        suggested_display_precision=0,
        translation_placeholders={"sensor_name": "BME280"},
    ),
    AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        key="BME280_temperature",
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=2,
        translation_placeholders={"sensor_name": "BME280"},
    ),
    AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.PRESSURE,
        key="BMP_pressure",
        translation_key="pressure",
        native_unit_of_measurement=UnitOfPressure.PA,
        suggested_unit_of_measurement=UnitOfPressure.MMHG,
        suggested_display_precision=0,
        translation_placeholders={"sensor_name": "BMP"},
    ),
    AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        key="BMP_temperature",
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=2,
        translation_placeholders={"sensor_name": "BMP"},
    ),
    AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        key="BMP280_temperature",
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=2,
        translation_placeholders={"sensor_name": "BMP280"},
    ),
    AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.PRESSURE,
        key="BMP280_pressure",
        translation_key="pressure",
        native_unit_of_measurement=UnitOfPressure.PA,
        suggested_unit_of_measurement=UnitOfPressure.MMHG,
        suggested_display_precision=0,
        translation_placeholders={"sensor_name": "BMP280"},
    ),
    AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.HUMIDITY,
        key="HTU21D_humidity",
        translation_key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=2,
        translation_placeholders={"sensor_name": "HTU21D"},
    ),
    AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        key="HTU21D_temperature",
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=2,
        translation_placeholders={"sensor_name": "HTU21D"},
    ),
    AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.PM10,
        translation_key="pm_10",
        key="SDS_P1",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        suggested_display_precision=2,
    ),
    AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.PM25,
        translation_key="pm_25",
        key="SDS_P2",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        suggested_display_precision=2,
    ),
    AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.HUMIDITY,
        key="SHT3X_humidity",
        translation_key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=2,
        translation_placeholders={"sensor_name": "SHT3X"},
    ),
    AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        key="SHT3X_temperature",
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=2,
        translation_placeholders={"sensor_name": "SHT3X"},
    ),
    AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        key="signal",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
    ),
    AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.SOUND_PRESSURE,
        key="PCBA_noiseMax",
        translation_key="noise_max",
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        suggested_display_precision=0,
    ),
    AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.SOUND_PRESSURE,
        key="PCBA_noiseAvg",
        translation_key="noise_avg",
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        suggested_display_precision=0,
    ),
    AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        translation_key="co2",
        key="CCS_CO2",
        suggested_display_precision=2,
        translation_placeholders={"sensor_name": "CCS"},
    ),
    AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        key="CCS_TVOC",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        suggested_display_precision=2,
    ),
    AltruistSensorEntityDescription(
        key="GC",
        native_unit_of_measurement="μR/h",
        translation_key="radiation",
        suggested_display_precision=2,
    ),
    AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.CO2,
        translation_key="co2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        key="SCD4x_co2",
        suggested_display_precision=2,
        translation_placeholders={"sensor_name": "SCD4x"},
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AltruistConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    coordinator = config_entry.runtime_data
    async_add_entities(
        AltruistSensor(coordinator, sensor_description)
        for sensor_description in SENSOR_DESCRIPTIONS
        if sensor_description.key in coordinator.data
    )


class AltruistSensor(CoordinatorEntity[AltruistDataUpdateCoordinator], SensorEntity):
    """Implementation of a Altruist sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AltruistDataUpdateCoordinator,
        description: AltruistSensorEntityDescription,
    ) -> None:
        """Initialize the Altruist sensor."""
        super().__init__(coordinator)
        self._device = coordinator.client.device
        self.entity_description: AltruistSensorEntityDescription = description
        self._attr_unique_id = f"{self._device.id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self._device.id)},
            manufacturer="Robonomics",
            model="Altruist",
            sw_version=self._device.fw_version,
            configuration_url=f"http://{self._device.ip_address}",
            serial_number=self._device.id,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available and self.entity_description.key in self.coordinator.data
        )

    @property
    def native_value(self) -> float | int:
        """Return the native value of the sensor."""
        string_value = self.coordinator.data[self.entity_description.key]
        return self.entity_description.native_value_fn(string_value)
