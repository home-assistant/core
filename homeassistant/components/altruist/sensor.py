"""Defines the Altruist sensor platform."""

from collections.abc import Callable
from dataclasses import dataclass
import logging

from altruistclient import AltruistDeviceModel

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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AltruistConfigEntry
from .const import DOMAIN
from .coordinator import AltruistDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class AltruistSensorEntityDescription(SensorEntityDescription):
    """Class to describe a Sensor entity."""

    native_value_fn: Callable[[str], float] = float
    state_class = SensorStateClass.MEASUREMENT


SENSOR_DESCRIPTIONS = {
    "BME280_humidity": AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.HUMIDITY,
        key="BME280_humidity",
        translation_key="bme_humidity",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=2,
    ),
    "BME280_pressure": AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.PRESSURE,
        key="BME280_pressure",
        translation_key="bme_pressure",
        native_unit_of_measurement=UnitOfPressure.MMHG,
        suggested_display_precision=0,
        native_value_fn=lambda string_value: float(string_value) * 0.0075,
    ),
    "BME280_temperature": AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        key="BME280_temperature",
        translation_key="bme_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=2,
    ),
    "BMP_pressure": AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.PRESSURE,
        key="BMP_pressure",
        translation_key="bmp_pressure",
        native_unit_of_measurement=UnitOfPressure.MMHG,
        suggested_display_precision=0,
        native_value_fn=lambda string_value: float(string_value) * 0.0075,
    ),
    "BMP_temperature": AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        key="BMP_temperature",
        translation_key="bmp_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=2,
    ),
    "BMP280_temperature": AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        key="BMP280_temperature",
        translation_key="bmp280_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=2,
    ),
    "BMP280_pressure": AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.PRESSURE,
        key="BMP280_pressure",
        translation_key="bmp280_pressure",
        native_unit_of_measurement=UnitOfPressure.MMHG,
        suggested_display_precision=0,
        native_value_fn=lambda string_value: float(string_value) * 0.0075,
    ),
    "HTU21D_humidity": AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.HUMIDITY,
        key="HTU21D_humidity",
        translation_key="htu_humidity",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=2,
    ),
    "HTU21D_temperature": AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        key="HTU21D_temperature",
        translation_key="htu_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=2,
    ),
    "SDS_P1": AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.PM10,
        translation_key="pm_10",
        key="SDS_P1",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        suggested_display_precision=2,
    ),
    "SDS_P2": AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.PM25,
        translation_key="pm_25",
        key="SDS_P2",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        suggested_display_precision=2,
    ),
    "SHT3X_humidity": AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.HUMIDITY,
        key="SHT3X_humidity",
        translation_key="sht_humidity",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=2,
    ),
    "SHT3X_temperature": AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        key="SHT3X_temperature",
        translation_key="sht_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=2,
    ),
    "signal": AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        key="signal",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
    ),
    "PCBA_noiseMax": AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.SOUND_PRESSURE,
        key="PCBA_noiseMax",
        translation_key="noise_max",
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        suggested_display_precision=0,
    ),
    "PCBA_noiseAvg": AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.SOUND_PRESSURE,
        key="PCBA_noiseAvg",
        translation_key="noise_avg",
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        suggested_display_precision=0,
    ),
    "CCS_CO2": AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        translation_key="ccs_co2",
        key="CCS_CO2",
        suggested_display_precision=2,
    ),
    "CCS_TVOC": AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        key="CCS_TVOC",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        suggested_display_precision=2,
    ),
    "GC": AltruistSensorEntityDescription(
        key="GC",
        native_unit_of_measurement="μR/h",
        translation_key="radiation",
        suggested_display_precision=2,
    ),
    "SCD4x_co2": AltruistSensorEntityDescription(
        device_class=SensorDeviceClass.CO2,
        translation_key="scd4x_co2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        key="SCD4x_co2",
        suggested_display_precision=2,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AltruistConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    coordinator: AltruistDataUpdateCoordinator = config_entry.runtime_data
    if coordinator.client is not None:
        async_add_entities(
            AltruistSensor(
                coordinator, coordinator.client.device, SENSOR_DESCRIPTIONS[sensor_name]
            )
            for sensor_name in coordinator.client.sensor_names
            if sensor_name in SENSOR_DESCRIPTIONS
        )


class AltruistSensor(CoordinatorEntity[AltruistDataUpdateCoordinator], SensorEntity):
    """Implementation of a Altruist sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AltruistDataUpdateCoordinator,
        device: AltruistDeviceModel,
        description: AltruistSensorEntityDescription,
    ) -> None:
        """Initialize the Altruist sensor."""
        super().__init__(coordinator)
        self._device = device
        self.entity_description: AltruistSensorEntityDescription = description
        self._attr_unique_id = (
            f"altruist_{self._device.id}-{self.entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device.id)},
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
