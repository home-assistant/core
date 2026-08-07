"""Centralized entity descriptions for all Solyx Energy Nymo entity platforms."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower

from .const import ATTRIBUTE_BOILER_POWER, ATTRIBUTE_ENERGY_BOILER, ATTRIBUTE_GRID_POWER
from .util import camel_to_snake

SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=ATTRIBUTE_BOILER_POWER,
        translation_key=camel_to_snake(ATTRIBUTE_BOILER_POWER),
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    SensorEntityDescription(
        key=ATTRIBUTE_ENERGY_BOILER,
        translation_key=camel_to_snake(ATTRIBUTE_ENERGY_BOILER),
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    ),
    SensorEntityDescription(
        key=ATTRIBUTE_GRID_POWER,
        translation_key=camel_to_snake(ATTRIBUTE_GRID_POWER),
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
)
