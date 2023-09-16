"""Support for AVM FRITZ!SmartHome temperature sensor only devices."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from pyfritzhome.fritzhomedevice import FritzhomeDevice

from homeassistant.components.climate import PRESET_COMFORT, PRESET_ECO
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utc_from_timestamp

from . import FritzBoxDeviceEntity
from .const import CONF_COORDINATOR, DOMAIN as FRITZBOX_DOMAIN
from .model import FritzEntityDescriptionMixinBase


@dataclass
class FritzEntityDescriptionMixinSensor(FritzEntityDescriptionMixinBase):
    """Sensor description mixin for Fritz!Smarthome entities."""

    native_value: Callable[[FritzhomeDevice], StateType | datetime]


@dataclass
class FritzSensorEntityDescription(
    SensorEntityDescription, FritzEntityDescriptionMixinSensor
):
    """Description for Fritz!Smarthome sensor entities."""

    entity_category_fn: Callable[[FritzhomeDevice], EntityCategory | None] | None = None


def suitable_eco_temperature(device: FritzhomeDevice) -> bool:
    """Check suitablity for eco temperature sensor."""
    return device.has_thermostat and device.eco_temperature is not None


def suitable_comfort_temperature(device: FritzhomeDevice) -> bool:
    """Check suitablity for comfort temperature sensor."""
    return device.has_thermostat and device.comfort_temperature is not None


def suitable_nextchange_temperature(device: FritzhomeDevice) -> bool:
    """Check suitablity for next scheduled temperature sensor."""
    return device.has_thermostat and device.nextchange_temperature is not None


def suitable_nextchange_time(device: FritzhomeDevice) -> bool:
    """Check suitablity for next scheduled changed time sensor."""
    return device.has_thermostat and device.nextchange_endperiod is not None


def suitable_temperature(device: FritzhomeDevice) -> bool:
    """Check suitablity for temperature sensor."""
    return device.has_temperature_sensor and not device.has_thermostat


def entity_category_temperature(device: FritzhomeDevice) -> EntityCategory | None:
    """Determine proper entity category for temperature sensor."""
    if device.has_switch or device.has_lightbulb:
        return EntityCategory.DIAGNOSTIC
    return None


def value_nextchange_preset(device: FritzhomeDevice) -> str:
    """Return native value for next scheduled preset sensor."""
    if device.nextchange_temperature == device.eco_temperature:
        return PRESET_ECO
    return PRESET_COMFORT


def value_scheduled_preset(device: FritzhomeDevice) -> str:
    """Return native value for current scheduled preset sensor."""
    if device.nextchange_temperature == device.eco_temperature:
        return PRESET_COMFORT
    return PRESET_ECO


SENSOR_TYPES: Final[tuple[FritzSensorEntityDescription, ...]] = (
    FritzSensorEntityDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category_fn=entity_category_temperature,
        suitable=suitable_temperature,
        native_value=lambda device: device.temperature,
    ),
    FritzSensorEntityDescription(
        key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        suitable=lambda device: device.rel_humidity is not None,
        native_value=lambda device: device.rel_humidity,
    ),
    FritzSensorEntityDescription(
        key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        suitable=lambda device: device.battery_level is not None,
        native_value=lambda device: device.battery_level,
    ),
    FritzSensorEntityDescription(
        key="power_consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suitable=lambda device: device.has_powermeter,
        native_value=lambda device: round((device.power or 0.0) / 1000, 3),
    ),
    FritzSensorEntityDescription(
        key="voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suitable=lambda device: device.has_powermeter,
        native_value=lambda device: round((device.voltage or 0.0) / 1000, 2),
    ),
    FritzSensorEntityDescription(
        key="electric_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suitable=lambda device: device.has_powermeter,
        native_value=lambda device: round((device.current or 0.0) / 1000, 3),
    ),
    FritzSensorEntityDescription(
        key="total_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suitable=lambda device: device.has_powermeter,
        native_value=lambda device: (device.energy or 0.0) / 1000,
    ),
    # Thermostat Sensors
    FritzSensorEntityDescription(
        key="comfort_temperature",
        translation_key="comfort_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        suitable=suitable_comfort_temperature,
        native_value=lambda device: device.comfort_temperature,
    ),
    FritzSensorEntityDescription(
        key="eco_temperature",
        translation_key="eco_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        suitable=suitable_eco_temperature,
        native_value=lambda device: device.eco_temperature,
    ),
    FritzSensorEntityDescription(
        key="nextchange_temperature",
        translation_key="nextchange_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        suitable=suitable_nextchange_temperature,
        native_value=lambda device: device.nextchange_temperature,
    ),
    FritzSensorEntityDescription(
        key="nextchange_time",
        translation_key="nextchange_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        suitable=suitable_nextchange_time,
        native_value=lambda device: utc_from_timestamp(device.nextchange_endperiod),
    ),
    FritzSensorEntityDescription(
        key="nextchange_preset",
        translation_key="nextchange_preset",
        entity_category=EntityCategory.DIAGNOSTIC,
        suitable=suitable_nextchange_temperature,
        native_value=value_nextchange_preset,
    ),
    FritzSensorEntityDescription(
        key="scheduled_preset",
        translation_key="scheduled_preset",
        entity_category=EntityCategory.DIAGNOSTIC,
        suitable=suitable_nextchange_temperature,
        native_value=value_scheduled_preset,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the FRITZ!SmartHome sensor from ConfigEntry."""
    coordinator = hass.data[FRITZBOX_DOMAIN][entry.entry_id][CONF_COORDINATOR]

    async_add_entities(
        [
            FritzBoxSensor(coordinator, ain, description)
            for ain, device in coordinator.data.devices.items()
            for description in SENSOR_TYPES
            if description.suitable(device)
        ]
    )


class FritzBoxSensor(FritzBoxDeviceEntity, SensorEntity):
    """The entity class for FRITZ!SmartHome sensors."""

    entity_description: FritzSensorEntityDescription

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.native_value(self.data)

    @property
    def entity_category(self) -> EntityCategory | None:
        """Return the category of the entity, if any."""
        if self.entity_description.entity_category_fn is not None:
            return self.entity_description.entity_category_fn(self.data)
        return super().entity_category
