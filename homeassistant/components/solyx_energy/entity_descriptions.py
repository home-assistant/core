"""Centralized entity descriptions for all Solyx Energy Nymo entity platforms."""

from dataclasses import dataclass

from homeassistant.components.number import NumberEntityDescription
from homeassistant.components.select import SelectEntityDescription
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower

from .const import (
    ATTRIBUTE_CONTROL_VALUE,
    ATTRIBUTE_ENERGY_BOILER,
    ATTRIBUTE_GRID_POWER,
    ATTRIBUTE_OPERATING_MODE,
    ATTRIBUTE_POWER_BOILER,
)
from .util import camel_to_snake


@dataclass(frozen=True, kw_only=True)
# pylint: disable-next=home-assistant-enforce-class-module
class SolyxSelectEntityDescription(SelectEntityDescription):
    """Description for a Solyx select entity with a device attribute to HA option mapping."""

    options_map: dict[str, str]


OPERATING_MODE_MAP = {"DIRECT": "direct", "MUTED": "muted"}

NUMBER_DESCRIPTIONS: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key=ATTRIBUTE_CONTROL_VALUE,
        translation_key=camel_to_snake(ATTRIBUTE_CONTROL_VALUE),
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:gauge",
    ),
)

SELECT_DESCRIPTIONS: tuple[SolyxSelectEntityDescription, ...] = (
    SolyxSelectEntityDescription(
        key=ATTRIBUTE_OPERATING_MODE,
        translation_key=camel_to_snake(ATTRIBUTE_OPERATING_MODE),
        options_map=OPERATING_MODE_MAP,
    ),
)

SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=ATTRIBUTE_POWER_BOILER,
        translation_key=camel_to_snake(ATTRIBUTE_POWER_BOILER),
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
