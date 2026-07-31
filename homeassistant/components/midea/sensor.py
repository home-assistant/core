"""Sensor for Midea Lan."""

from dataclasses import dataclass
from typing import cast, override

from midealocal.device import MideaDevice

from homeassistant.components.sensor import (
    EntityCategory,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    REVOLUTIONS_PER_MINUTE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfRatio,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .device_catalog import DeviceType
from .entity import MideaEntity

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class MideaSensorEntityDescription(SensorEntityDescription):
    """Description for a Midea sensor entity."""

    models: list[DeviceType]


SENSOR_ENTITIES: list[MideaSensorEntityDescription] = [
    MideaSensorEntityDescription(
        key="indoor_humidity",
        translation_key="indoor_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        models=[DeviceType.AC],
    ),
    MideaSensorEntityDescription(
        key="indoor_temperature",
        translation_key="indoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        models=[DeviceType.AC],
    ),
    MideaSensorEntityDescription(
        key="outdoor_temperature",
        translation_key="outdoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        models=[DeviceType.AC],
    ),
    MideaSensorEntityDescription(
        key="total_energy_consumption",
        translation_key="total_energy_consumption",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        models=[DeviceType.AC],
    ),
    MideaSensorEntityDescription(
        key="current_energy_consumption",
        translation_key="current_energy_consumption",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        models=[DeviceType.AC],
    ),
    MideaSensorEntityDescription(
        key="realtime_power",
        translation_key="realtime_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        models=[DeviceType.AC],
    ),
    MideaSensorEntityDescription(
        key="pmv",
        translation_key="pmv",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        models=[DeviceType.AC],
    ),
    MideaSensorEntityDescription(
        key="error_code",
        translation_key="error_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        models=[DeviceType.AC],
    ),
    MideaSensorEntityDescription(
        key="compressor_frequency",
        translation_key="compressor_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        models=[DeviceType.AC],
    ),
    MideaSensorEntityDescription(
        key="target_compressor_frequency",
        translation_key="target_compressor_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        models=[DeviceType.AC],
    ),
    MideaSensorEntityDescription(
        key="compressor_current",
        translation_key="compressor_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        models=[DeviceType.AC],
    ),
    MideaSensorEntityDescription(
        key="compressor_voltage",
        translation_key="compressor_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        models=[DeviceType.AC],
    ),
    MideaSensorEntityDescription(
        key="indoor_coil_temperature",
        translation_key="indoor_coil_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        models=[DeviceType.AC],
    ),
    MideaSensorEntityDescription(
        key="evaporator_temperature",
        translation_key="evaporator_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        models=[DeviceType.AC],
    ),
    MideaSensorEntityDescription(
        key="condenser_temperature",
        translation_key="condenser_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        models=[DeviceType.AC],
    ),
    MideaSensorEntityDescription(
        key="outdoor_ambient_temperature",
        translation_key="outdoor_ambient_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        models=[DeviceType.AC],
    ),
    MideaSensorEntityDescription(
        key="discharge_pipe_temperature",
        translation_key="discharge_pipe_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        models=[DeviceType.AC],
    ),
    MideaSensorEntityDescription(
        key="indoor_fan_speed",
        translation_key="indoor_fan_speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        models=[DeviceType.AC],
    ),
    MideaSensorEntityDescription(
        key="target_indoor_fan_speed",
        translation_key="target_indoor_fan_speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        models=[DeviceType.AC],
    ),
    MideaSensorEntityDescription(
        key="compressor_power",
        translation_key="compressor_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        models=[DeviceType.AC],
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors for device."""
    device = config_entry.runtime_data

    sensors: list[MideaSensor] = [
        MideaSensor(device, description)
        for description in SENSOR_ENTITIES
        if device.device_type in description.models
        and description.key in device.attributes
    ]

    async_add_entities(sensors)


class MideaSensor(MideaEntity, SensorEntity):
    """Represent a Midea  sensor."""

    _entity_key: str

    def __init__(
        self,
        device: MideaDevice,
        description: SensorEntityDescription,
    ) -> None:
        """Midea Sensor entity init."""
        self._entity_key = description.key
        super().__init__(device, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> StateType:
        """Native value of the sensor."""
        value = self._device.get_attribute(self._entity_key)
        return cast("StateType", value)
