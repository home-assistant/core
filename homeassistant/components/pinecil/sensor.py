"""Sensor platform for Pinecil integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pynecil import LiveDataResponse, OperatingMode, PowerSource

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import PinecilConfigEntry
from .const import OHM
from .entity import PinecilBaseEntity


class PinecilSensor(StrEnum):
    """Pinecil Sensors."""

    LIVE_TEMP = "live_temperature"
    SETPOINT_TEMP = "setpoint_temperature"
    DC_VOLTAGE = "voltage"
    HANDLETEMP = "handle_temperature"
    PWMLEVEL = "power_pwm_level"
    POWER_SRC = "power_source"
    TIP_RESISTANCE = "tip_resistance"
    UPTIME = "uptime"
    MOVEMENT_TIME = "movement_time"
    MAX_TIP_TEMP_ABILITY = "max_tip_temp_ability"
    TIP_VOLTAGE = "tip_voltage"
    HALL_SENSOR = "hall_sensor"
    OPERATING_MODE = "operating_mode"
    ESTIMATED_POWER = "estimated_power"


@dataclass(frozen=True, kw_only=True)
class PinecilSensorEntityDescription(SensorEntityDescription):
    """Pinecil sensor entity descriptions."""

    value_fn: Callable[[LiveDataResponse], Any]


SENSOR_DESCRIPTIONS: tuple[PinecilSensorEntityDescription, ...] = (
    PinecilSensorEntityDescription(
        key=PinecilSensor.LIVE_TEMP,
        translation_key=PinecilSensor.LIVE_TEMP,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.live_temp,
    ),
    PinecilSensorEntityDescription(
        key=PinecilSensor.DC_VOLTAGE,
        translation_key=PinecilSensor.DC_VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.dc_input,
    ),
    PinecilSensorEntityDescription(
        key=PinecilSensor.HANDLETEMP,
        translation_key=PinecilSensor.HANDLETEMP,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.handle_temp,
    ),
    PinecilSensorEntityDescription(
        key=PinecilSensor.PWMLEVEL,
        translation_key=PinecilSensor.PWMLEVEL,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.power_level,
    ),
    PinecilSensorEntityDescription(
        key=PinecilSensor.POWER_SRC,
        translation_key=PinecilSensor.POWER_SRC,
        device_class=SensorDeviceClass.ENUM,
        options=[item.lower() for item in PowerSource._member_names_],
        value_fn=lambda data: data.power_src.name.lower() if data.power_src else None,
    ),
    PinecilSensorEntityDescription(
        key=PinecilSensor.TIP_RESISTANCE,
        translation_key=PinecilSensor.TIP_RESISTANCE,
        native_unit_of_measurement=OHM,
        value_fn=lambda data: data.tip_res,
    ),
    PinecilSensorEntityDescription(
        key=PinecilSensor.UPTIME,
        translation_key=PinecilSensor.UPTIME,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.uptime,
    ),
    PinecilSensorEntityDescription(
        key=PinecilSensor.MOVEMENT_TIME,
        translation_key=PinecilSensor.MOVEMENT_TIME,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.movement,
    ),
    PinecilSensorEntityDescription(
        key=PinecilSensor.MAX_TIP_TEMP_ABILITY,
        translation_key=PinecilSensor.MAX_TIP_TEMP_ABILITY,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        value_fn=lambda data: data.max_temp,
    ),
    PinecilSensorEntityDescription(
        key=PinecilSensor.TIP_VOLTAGE,
        translation_key=PinecilSensor.TIP_VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda data: data.raw_tip,
    ),
    PinecilSensorEntityDescription(
        key=PinecilSensor.HALL_SENSOR,
        translation_key=PinecilSensor.HALL_SENSOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.hall_sensor,
    ),
    PinecilSensorEntityDescription(
        key=PinecilSensor.OPERATING_MODE,
        translation_key=PinecilSensor.OPERATING_MODE,
        device_class=SensorDeviceClass.ENUM,
        options=[item.lower() for item in OperatingMode._member_names_],
        value_fn=lambda data: data.op_mode.name.lower() if data.op_mode else None,
    ),
    PinecilSensorEntityDescription(
        key=PinecilSensor.ESTIMATED_POWER,
        translation_key=PinecilSensor.ESTIMATED_POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.est_power,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PinecilConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        PinecilSensorEntity(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class PinecilSensorEntity(PinecilBaseEntity, SensorEntity):
    """Representation of a Pinecil sensor entity."""

    _attr_has_entity_name = True
    entity_description: PinecilSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return sensor state."""
        return self.entity_description.value_fn(self.coordinator.data)
