"""Sensor for Shelly."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, cast

from aioshelly.block_device import Block

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorExtraStoredData,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import RegistryEntry
from homeassistant.helpers.typing import StateType

from .const import CONF_SLEEP_PERIOD, SHAIR_MAX_WORK_HOURS
from .coordinator import ShellyBlockCoordinator, ShellyRpcCoordinator
from .entity import (
    BlockEntityDescription,
    RestEntityDescription,
    RpcEntityDescription,
    ShellyBlockAttributeEntity,
    ShellyRestAttributeEntity,
    ShellyRpcAttributeEntity,
    ShellySleepingBlockAttributeEntity,
    ShellySleepingRpcAttributeEntity,
    async_setup_entry_attribute_entities,
    async_setup_entry_rest,
    async_setup_entry_rpc,
)
from .utils import get_device_entry_gen, get_device_uptime


@dataclass
class BlockSensorDescription(BlockEntityDescription, SensorEntityDescription):
    """Class to describe a BLOCK sensor."""


@dataclass
class RpcSensorDescription(RpcEntityDescription, SensorEntityDescription):
    """Class to describe a RPC sensor."""


@dataclass
class RestSensorDescription(RestEntityDescription, SensorEntityDescription):
    """Class to describe a REST sensor."""


SENSORS: Final = {
    ("device", "battery"): BlockSensorDescription(
        key="device|battery",
        name="Battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        removal_condition=lambda settings, _: settings.get("external_power") == 1,
        available=lambda block: cast(int, block.battery) != -1,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ("device", "deviceTemp"): BlockSensorDescription(
        key="device|deviceTemp",
        name="Device temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ("emeter", "current"): BlockSensorDescription(
        key="emeter|current",
        name="Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("device", "neutralCurrent"): BlockSensorDescription(
        key="device|neutralCurrent",
        name="Neutral current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    ("light", "power"): BlockSensorDescription(
        key="light|power",
        name="Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    ("device", "power"): BlockSensorDescription(
        key="device|power",
        name="Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("emeter", "power"): BlockSensorDescription(
        key="emeter|power",
        name="Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("device", "voltage"): BlockSensorDescription(
        key="device|voltage",
        name="Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    ("emeter", "voltage"): BlockSensorDescription(
        key="emeter|voltage",
        name="Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("emeter", "powerFactor"): BlockSensorDescription(
        key="emeter|powerFactor",
        name="Power factor",
        suggested_display_precision=2,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("relay", "power"): BlockSensorDescription(
        key="relay|power",
        name="Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("roller", "rollerPower"): BlockSensorDescription(
        key="roller|rollerPower",
        name="Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("device", "energy"): BlockSensorDescription(
        key="device|energy",
        name="Energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda value: value / 60,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ("emeter", "energy"): BlockSensorDescription(
        key="emeter|energy",
        name="Energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        available=lambda block: cast(int, block.energy) != -1,
    ),
    ("emeter", "energyReturned"): BlockSensorDescription(
        key="emeter|energyReturned",
        name="Energy returned",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        available=lambda block: cast(int, block.energyReturned) != -1,
    ),
    ("light", "energy"): BlockSensorDescription(
        key="light|energy",
        name="Energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda value: value / 60,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ("relay", "energy"): BlockSensorDescription(
        key="relay|energy",
        name="Energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda value: value / 60,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ("roller", "rollerEnergy"): BlockSensorDescription(
        key="roller|rollerEnergy",
        name="Energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda value: value / 60,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ("sensor", "concentration"): BlockSensorDescription(
        key="sensor|concentration",
        name="Gas concentration",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        icon="mdi:gauge",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("sensor", "temp"): BlockSensorDescription(
        key="sensor|temp",
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ("sensor", "extTemp"): BlockSensorDescription(
        key="sensor|extTemp",
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        available=lambda block: cast(int, block.extTemp) != 999
        and not getattr(block, "sensorError", False),
    ),
    ("sensor", "humidity"): BlockSensorDescription(
        key="sensor|humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        available=lambda block: cast(int, block.humidity) != 999
        and not getattr(block, "sensorError", False),
    ),
    ("sensor", "luminosity"): BlockSensorDescription(
        key="sensor|luminosity",
        name="Luminosity",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        available=lambda block: cast(int, block.luminosity) != -1,
    ),
    ("sensor", "tilt"): BlockSensorDescription(
        key="sensor|tilt",
        name="Tilt",
        native_unit_of_measurement=DEGREE,
        icon="mdi:angle-acute",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("relay", "totalWorkTime"): BlockSensorDescription(
        key="relay|totalWorkTime",
        name="Lamp life",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:progress-wrench",
        value=lambda value: 100 - (value / 3600 / SHAIR_MAX_WORK_HOURS),
        suggested_display_precision=1,
        extra_state_attributes=lambda block: {
            "Operational hours": round(cast(int, block.totalWorkTime) / 3600, 1)
        },
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ("adc", "adc"): BlockSensorDescription(
        key="adc|adc",
        name="ADC",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("sensor", "sensorOp"): BlockSensorDescription(
        key="sensor|sensorOp",
        name="Operation",
        device_class=SensorDeviceClass.ENUM,
        options=["unknown", "warmup", "normal", "fault"],
        translation_key="operation",
        icon="mdi:cog-transfer",
        value=lambda value: value,
        extra_state_attributes=lambda block: {"self_test": block.selfTest},
    ),
}

REST_SENSORS: Final = {
    "rssi": RestSensorDescription(
        key="rssi",
        name="RSSI",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        value=lambda status, _: status["wifi_sta"]["rssi"],
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "uptime": RestSensorDescription(
        key="uptime",
        name="Uptime",
        value=lambda status, last: get_device_uptime(status["uptime"], last),
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}


RPC_SENSORS: Final = {
    "power": RpcSensorDescription(
        key="switch",
        sub_key="apower",
        name="Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "power_pm1": RpcSensorDescription(
        key="pm1",
        sub_key="apower",
        name="Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "a_act_power": RpcSensorDescription(
        key="em",
        sub_key="a_act_power",
        name="Phase A active power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "b_act_power": RpcSensorDescription(
        key="em",
        sub_key="b_act_power",
        name="Phase B active power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "c_act_power": RpcSensorDescription(
        key="em",
        sub_key="c_act_power",
        name="Phase C active power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "total_act_power": RpcSensorDescription(
        key="em",
        sub_key="total_act_power",
        name="Total active power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "a_aprt_power": RpcSensorDescription(
        key="em",
        sub_key="a_aprt_power",
        name="Phase A apparent power",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "b_aprt_power": RpcSensorDescription(
        key="em",
        sub_key="b_aprt_power",
        name="Phase B apparent power",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "c_aprt_power": RpcSensorDescription(
        key="em",
        sub_key="c_aprt_power",
        name="Phase C apparent power",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "total_aprt_power": RpcSensorDescription(
        key="em",
        sub_key="total_aprt_power",
        name="Total apparent power",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "a_pf": RpcSensorDescription(
        key="em",
        sub_key="a_pf",
        name="Phase A power factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "b_pf": RpcSensorDescription(
        key="em",
        sub_key="b_pf",
        name="Phase B power factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "c_pf": RpcSensorDescription(
        key="em",
        sub_key="c_pf",
        name="Phase C power factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "voltage": RpcSensorDescription(
        key="switch",
        sub_key="voltage",
        name="Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value=lambda status, _: None if status is None else float(status),
        suggested_display_precision=1,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "voltage_pm1": RpcSensorDescription(
        key="pm1",
        sub_key="voltage",
        name="Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value=lambda status, _: None if status is None else float(status),
        suggested_display_precision=1,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "a_voltage": RpcSensorDescription(
        key="em",
        sub_key="a_voltage",
        name="Phase A voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "b_voltage": RpcSensorDescription(
        key="em",
        sub_key="b_voltage",
        name="Phase B voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "c_voltage": RpcSensorDescription(
        key="em",
        sub_key="c_voltage",
        name="Phase C voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "current": RpcSensorDescription(
        key="switch",
        sub_key="current",
        name="Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value=lambda status, _: None if status is None else float(status),
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "current_pm1": RpcSensorDescription(
        key="pm1",
        sub_key="current",
        name="Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value=lambda status, _: None if status is None else float(status),
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "a_current": RpcSensorDescription(
        key="em",
        sub_key="a_current",
        name="Phase A current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "b_current": RpcSensorDescription(
        key="em",
        sub_key="b_current",
        name="Phase B current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "c_current": RpcSensorDescription(
        key="em",
        sub_key="c_current",
        name="Phase C current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "n_current": RpcSensorDescription(
        key="em",
        sub_key="n_current",
        name="Phase N current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        available=lambda status: status["n_current"] is not None,
        entity_registry_enabled_default=False,
    ),
    "total_current": RpcSensorDescription(
        key="em",
        sub_key="total_current",
        name="Total current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "energy": RpcSensorDescription(
        key="switch",
        sub_key="aenergy",
        name="Energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: status["total"],
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "energy_pm1": RpcSensorDescription(
        key="pm1",
        sub_key="aenergy",
        name="Energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: status["total"],
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "total_act": RpcSensorDescription(
        key="emdata",
        sub_key="total_act",
        name="Total active energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: float(status),
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "a_total_act_energy": RpcSensorDescription(
        key="emdata",
        sub_key="a_total_act_energy",
        name="Phase A total active energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: float(status),
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    "b_total_act_energy": RpcSensorDescription(
        key="emdata",
        sub_key="b_total_act_energy",
        name="Phase B total active energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: float(status),
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    "c_total_act_energy": RpcSensorDescription(
        key="emdata",
        sub_key="c_total_act_energy",
        name="Phase C total active energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: float(status),
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    "total_act_ret": RpcSensorDescription(
        key="emdata",
        sub_key="total_act_ret",
        name="Total active returned energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: float(status),
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "a_total_act_ret_energy": RpcSensorDescription(
        key="emdata",
        sub_key="a_total_act_ret_energy",
        name="Phase A total active returned energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: float(status),
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    "b_total_act_ret_energy": RpcSensorDescription(
        key="emdata",
        sub_key="b_total_act_ret_energy",
        name="Phase B total active returned energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: float(status),
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    "c_total_act_ret_energy": RpcSensorDescription(
        key="emdata",
        sub_key="c_total_act_ret_energy",
        name="Phase C total active returned energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda status, _: float(status),
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    "freq": RpcSensorDescription(
        key="switch",
        sub_key="freq",
        name="Frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "freq_pm1": RpcSensorDescription(
        key="pm1",
        sub_key="freq",
        name="Frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "a_freq": RpcSensorDescription(
        key="em",
        sub_key="a_freq",
        name="Phase A frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "b_freq": RpcSensorDescription(
        key="em",
        sub_key="b_freq",
        name="Phase B frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "c_freq": RpcSensorDescription(
        key="em",
        sub_key="c_freq",
        name="Phase C frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "illuminance": RpcSensorDescription(
        key="illuminance",
        sub_key="lux",
        name="Illuminance",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "temperature": RpcSensorDescription(
        key="switch",
        sub_key="temperature",
        name="Device temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value=lambda status, _: status["tC"],
        suggested_display_precision=1,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        use_polling_coordinator=True,
    ),
    "temperature_0": RpcSensorDescription(
        key="temperature",
        sub_key="tC",
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "rssi": RpcSensorDescription(
        key="wifi",
        sub_key="rssi",
        name="RSSI",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        use_polling_coordinator=True,
    ),
    "uptime": RpcSensorDescription(
        key="sys",
        sub_key="uptime",
        name="Uptime",
        value=get_device_uptime,
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        use_polling_coordinator=True,
    ),
    "humidity_0": RpcSensorDescription(
        key="humidity",
        sub_key="rh",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "battery": RpcSensorDescription(
        key="devicepower:0",
        sub_key="battery",
        name="Battery",
        native_unit_of_measurement=PERCENTAGE,
        value=lambda status, _: status["percent"],
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "voltmeter": RpcSensorDescription(
        key="voltmeter",
        sub_key="voltage",
        name="Voltmeter",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value=lambda status, _: float(status),
        suggested_display_precision=2,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        available=lambda status: status is not None,
    ),
    "analoginput": RpcSensorDescription(
        key="input",
        sub_key="percent",
        name="Analog input",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


def _build_block_description(entry: RegistryEntry) -> BlockSensorDescription:
    """Build description when restoring block attribute entities."""
    return BlockSensorDescription(
        key="",
        name="",
        icon=entry.original_icon,
        native_unit_of_measurement=entry.unit_of_measurement,
        device_class=entry.original_device_class,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for device."""
    if get_device_entry_gen(config_entry) == 2:
        if config_entry.data[CONF_SLEEP_PERIOD]:
            async_setup_entry_rpc(
                hass,
                config_entry,
                async_add_entities,
                RPC_SENSORS,
                RpcSleepingSensor,
            )
        else:
            async_setup_entry_rpc(
                hass, config_entry, async_add_entities, RPC_SENSORS, RpcSensor
            )
        return

    if config_entry.data[CONF_SLEEP_PERIOD]:
        async_setup_entry_attribute_entities(
            hass,
            config_entry,
            async_add_entities,
            SENSORS,
            BlockSleepingSensor,
            _build_block_description,
        )
    else:
        async_setup_entry_attribute_entities(
            hass,
            config_entry,
            async_add_entities,
            SENSORS,
            BlockSensor,
            _build_block_description,
        )
        async_setup_entry_rest(
            hass, config_entry, async_add_entities, REST_SENSORS, RestSensor
        )


class BlockSensor(ShellyBlockAttributeEntity, SensorEntity):
    """Represent a block sensor."""

    entity_description: BlockSensorDescription

    def __init__(
        self,
        coordinator: ShellyBlockCoordinator,
        block: Block,
        attribute: str,
        description: BlockSensorDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, block, attribute, description)

        self._attr_native_unit_of_measurement = description.native_unit_of_measurement

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        return self.attribute_value


class RestSensor(ShellyRestAttributeEntity, SensorEntity):
    """Represent a REST sensor."""

    entity_description: RestSensorDescription

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        return self.attribute_value


class RpcSensor(ShellyRpcAttributeEntity, SensorEntity):
    """Represent a RPC sensor."""

    entity_description: RpcSensorDescription

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        return self.attribute_value


class BlockSleepingSensor(ShellySleepingBlockAttributeEntity, RestoreSensor):
    """Represent a block sleeping sensor."""

    entity_description: BlockSensorDescription

    def __init__(
        self,
        coordinator: ShellyBlockCoordinator,
        block: Block | None,
        attribute: str,
        description: BlockSensorDescription,
        entry: RegistryEntry | None = None,
        sensors: Mapping[tuple[str, str], BlockSensorDescription] | None = None,
    ) -> None:
        """Initialize the sleeping sensor."""
        super().__init__(coordinator, block, attribute, description, entry, sensors)
        self.restored_data: SensorExtraStoredData | None = None

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self.restored_data = await self.async_get_last_sensor_data()

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        if self.block is not None:
            return self.attribute_value

        if self.restored_data is None:
            return None

        return cast(StateType, self.restored_data.native_value)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor, if any."""
        if self.block is not None:
            return self.entity_description.native_unit_of_measurement

        if self.restored_data is None:
            return None

        return self.restored_data.native_unit_of_measurement


class RpcSleepingSensor(ShellySleepingRpcAttributeEntity, RestoreSensor):
    """Represent a RPC sleeping sensor."""

    entity_description: RpcSensorDescription

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        attribute: str,
        description: RpcEntityDescription,
        entry: RegistryEntry | None = None,
    ) -> None:
        """Initialize the sleeping sensor."""
        super().__init__(coordinator, key, attribute, description, entry)
        self.restored_data: SensorExtraStoredData | None = None

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self.restored_data = await self.async_get_last_sensor_data()

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        if self.coordinator.device.initialized:
            return self.attribute_value

        if self.restored_data is None:
            return None

        return cast(StateType, self.restored_data.native_value)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor, if any."""
        return self.entity_description.native_unit_of_measurement
