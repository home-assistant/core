"""SMA Solar Webconnect interface."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pysma

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    POWER_VOLT_AMPERE_REACTIVE,
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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, PYSMA_COORDINATOR, PYSMA_DEVICE_INFO, PYSMA_SENSORS

SENSOR_ENTITIES: dict[str, SensorEntityDescription] = {
    "status": SensorEntityDescription(
        key="status",
        name="Status",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "operating_status_general": SensorEntityDescription(
        key="operating_status_general",
        name="Operating Status General",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "inverter_condition": SensorEntityDescription(
        key="inverter_condition",
        name="Inverter Condition",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "inverter_system_init": SensorEntityDescription(
        key="inverter_system_init",
        name="Inverter System Init",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "grid_connection_status": SensorEntityDescription(
        key="grid_connection_status",
        name="Grid Connection Status",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "grid_relay_status": SensorEntityDescription(
        key="grid_relay_status",
        name="Grid Relay Status",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "pv_power_a": SensorEntityDescription(
        key="pv_power_a",
        name="PV Power A",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    "pv_power_b": SensorEntityDescription(
        key="pv_power_b",
        name="PV Power B",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    "pv_power_c": SensorEntityDescription(
        key="pv_power_c",
        name="PV Power C",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
    ),
    "pv_voltage_a": SensorEntityDescription(
        key="pv_voltage_a",
        name="PV Voltage A",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
    ),
    "pv_voltage_b": SensorEntityDescription(
        key="pv_voltage_b",
        name="PV Voltage B",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
    ),
    "pv_voltage_c": SensorEntityDescription(
        key="pv_voltage_c",
        name="PV Voltage C",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
    ),
    "pv_current_a": SensorEntityDescription(
        key="pv_current_a",
        name="PV Current A",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    "pv_current_b": SensorEntityDescription(
        key="pv_current_b",
        name="PV Current B",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    "pv_current_c": SensorEntityDescription(
        key="pv_current_c",
        name="PV Current C",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
    ),
    "insulation_residual_current": SensorEntityDescription(
        key="insulation_residual_current",
        name="Insulation Residual Current",
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
    ),
    "grid_power": SensorEntityDescription(
        key="grid_power",
        name="Grid Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    "frequency": SensorEntityDescription(
        key="frequency",
        name="Frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.FREQUENCY,
        entity_registry_enabled_default=False,
    ),
    "power_l1": SensorEntityDescription(
        key="power_l1",
        name="Power L1",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
    ),
    "power_l2": SensorEntityDescription(
        key="power_l2",
        name="Power L2",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
    ),
    "power_l3": SensorEntityDescription(
        key="power_l3",
        name="Power L3",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
    ),
    "grid_reactive_power": SensorEntityDescription(
        key="grid_reactive_power",
        name="Grid Reactive Power",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        entity_registry_enabled_default=False,
    ),
    "grid_reactive_power_l1": SensorEntityDescription(
        key="grid_reactive_power_l1",
        name="Grid Reactive Power L1",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        entity_registry_enabled_default=False,
    ),
    "grid_reactive_power_l2": SensorEntityDescription(
        key="grid_reactive_power_l2",
        name="Grid Reactive Power L2",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        entity_registry_enabled_default=False,
    ),
    "grid_reactive_power_l3": SensorEntityDescription(
        key="grid_reactive_power_l3",
        name="Grid Reactive Power L3",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        entity_registry_enabled_default=False,
    ),
    "grid_apparent_power": SensorEntityDescription(
        key="grid_apparent_power",
        name="Grid Apparent Power",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.APPARENT_POWER,
        entity_registry_enabled_default=False,
    ),
    "grid_apparent_power_l1": SensorEntityDescription(
        key="grid_apparent_power_l1",
        name="Grid Apparent Power L1",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.APPARENT_POWER,
        entity_registry_enabled_default=False,
    ),
    "grid_apparent_power_l2": SensorEntityDescription(
        key="grid_apparent_power_l2",
        name="Grid Apparent Power L2",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.APPARENT_POWER,
        entity_registry_enabled_default=False,
    ),
    "grid_apparent_power_l3": SensorEntityDescription(
        key="grid_apparent_power_l3",
        name="Grid Apparent Power L3",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.APPARENT_POWER,
        entity_registry_enabled_default=False,
    ),
    "grid_power_factor": SensorEntityDescription(
        key="grid_power_factor",
        name="Grid Power Factor",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER_FACTOR,
        entity_registry_enabled_default=False,
    ),
    "grid_power_factor_excitation": SensorEntityDescription(
        key="grid_power_factor_excitation",
        name="Grid Power Factor Excitation",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER_FACTOR,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "current_l1": SensorEntityDescription(
        key="current_l1",
        name="Current L1",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
    ),
    "current_l2": SensorEntityDescription(
        key="current_l2",
        name="Current L2",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
    ),
    "current_l3": SensorEntityDescription(
        key="current_l3",
        name="Current L3",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
    ),
    "current_total": SensorEntityDescription(
        key="current_total",
        name="Current Total",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    "voltage_l1": SensorEntityDescription(
        key="voltage_l1",
        name="Voltage L1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
    ),
    "voltage_l2": SensorEntityDescription(
        key="voltage_l2",
        name="Voltage L2",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
    ),
    "voltage_l3": SensorEntityDescription(
        key="voltage_l3",
        name="Voltage L3",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
    ),
    "total_yield": SensorEntityDescription(
        key="total_yield",
        name="Total Yield",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
    ),
    "daily_yield": SensorEntityDescription(
        key="daily_yield",
        name="Daily Yield",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
    ),
    "metering_power_supplied": SensorEntityDescription(
        key="metering_power_supplied",
        name="Metering Power Supplied",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    "metering_power_absorbed": SensorEntityDescription(
        key="metering_power_absorbed",
        name="Metering Power Absorbed",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    "metering_frequency": SensorEntityDescription(
        key="metering_frequency",
        name="Metering Frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.FREQUENCY,
    ),
    "metering_total_yield": SensorEntityDescription(
        key="metering_total_yield",
        name="Metering Total Yield",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
    ),
    "metering_total_absorbed": SensorEntityDescription(
        key="metering_total_absorbed",
        name="Metering Total Absorbed",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
    ),
    "metering_current_l1": SensorEntityDescription(
        key="metering_current_l1",
        name="Metering Current L1",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    "metering_current_l2": SensorEntityDescription(
        key="metering_current_l2",
        name="Metering Current L2",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    "metering_current_l3": SensorEntityDescription(
        key="metering_current_l3",
        name="Metering Current L3",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    "metering_voltage_l1": SensorEntityDescription(
        key="metering_voltage_l1",
        name="Metering Voltage L1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
    ),
    "metering_voltage_l2": SensorEntityDescription(
        key="metering_voltage_l2",
        name="Metering Voltage L2",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
    ),
    "metering_voltage_l3": SensorEntityDescription(
        key="metering_voltage_l3",
        name="Metering Voltage L3",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
    ),
    "metering_active_power_feed_l1": SensorEntityDescription(
        key="metering_active_power_feed_l1",
        name="Metering Active Power Feed L1",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    "metering_active_power_feed_l2": SensorEntityDescription(
        key="metering_active_power_feed_l2",
        name="Metering Active Power Feed L2",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    "metering_active_power_feed_l3": SensorEntityDescription(
        key="metering_active_power_feed_l3",
        name="Metering Active Power Feed L3",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    "metering_active_power_draw_l1": SensorEntityDescription(
        key="metering_active_power_draw_l1",
        name="Metering Active Power Draw L1",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    "metering_active_power_draw_l2": SensorEntityDescription(
        key="metering_active_power_draw_l2",
        name="Metering Active Power Draw L2",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    "metering_active_power_draw_l3": SensorEntityDescription(
        key="metering_active_power_draw_l3",
        name="Metering Active Power Draw L3",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    "metering_current_consumption": SensorEntityDescription(
        key="metering_current_consumption",
        name="Metering Current Consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
    ),
    "metering_total_consumption": SensorEntityDescription(
        key="metering_total_consumption",
        name="Metering Total Consumption",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        entity_registry_enabled_default=False,
    ),
    "pv_gen_meter": SensorEntityDescription(
        key="pv_gen_meter",
        name="PV Gen Meter",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
    ),
    "optimizer_power": SensorEntityDescription(
        key="optimizer_power",
        name="Optimizer Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    "optimizer_current": SensorEntityDescription(
        key="optimizer_current",
        name="Optimizer Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
    ),
    "optimizer_voltage": SensorEntityDescription(
        key="optimizer_voltage",
        name="Optimizer Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
    ),
    "optimizer_temp": SensorEntityDescription(
        key="optimizer_temp",
        name="Optimizer Temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
    ),
    "battery_soc_total": SensorEntityDescription(
        key="battery_soc_total",
        name="Battery SOC Total",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
    ),
    "battery_soc_a": SensorEntityDescription(
        key="battery_soc_a",
        name="Battery SOC A",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        entity_registry_enabled_default=False,
    ),
    "battery_soc_b": SensorEntityDescription(
        key="battery_soc_b",
        name="Battery SOC B",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        entity_registry_enabled_default=False,
    ),
    "battery_soc_c": SensorEntityDescription(
        key="battery_soc_c",
        name="Battery SOC C",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        entity_registry_enabled_default=False,
    ),
    "battery_voltage_a": SensorEntityDescription(
        key="battery_voltage_a",
        name="Battery Voltage A",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
    ),
    "battery_voltage_b": SensorEntityDescription(
        key="battery_voltage_b",
        name="Battery Voltage B",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
    ),
    "battery_voltage_c": SensorEntityDescription(
        key="battery_voltage_c",
        name="Battery Voltage C",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
    ),
    "battery_current_a": SensorEntityDescription(
        key="battery_current_a",
        name="Battery Current A",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    "battery_current_b": SensorEntityDescription(
        key="battery_current_b",
        name="Battery Current B",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    "battery_current_c": SensorEntityDescription(
        key="battery_current_c",
        name="Battery Current C",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    "battery_temp_a": SensorEntityDescription(
        key="battery_temp_a",
        name="Battery Temp A",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    "battery_temp_b": SensorEntityDescription(
        key="battery_temp_b",
        name="Battery Temp B",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    "battery_temp_c": SensorEntityDescription(
        key="battery_temp_c",
        name="Battery Temp C",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    "battery_status_operating_mode": SensorEntityDescription(
        key="battery_status_operating_mode",
        name="Battery Status Operating Mode",
    ),
    "battery_capacity_total": SensorEntityDescription(
        key="battery_capacity_total",
        name="Battery Capacity Total",
        native_unit_of_measurement=PERCENTAGE,
    ),
    "battery_capacity_a": SensorEntityDescription(
        key="battery_capacity_a",
        name="Battery Capacity A",
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
    ),
    "battery_capacity_b": SensorEntityDescription(
        key="battery_capacity_b",
        name="Battery Capacity B",
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
    ),
    "battery_capacity_c": SensorEntityDescription(
        key="battery_capacity_c",
        name="Battery Capacity C",
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
    ),
    "battery_charging_voltage_a": SensorEntityDescription(
        key="battery_charging_voltage_a",
        name="Battery Charging Voltage A",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
    ),
    "battery_charging_voltage_b": SensorEntityDescription(
        key="battery_charging_voltage_b",
        name="Battery Charging Voltage B",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
    ),
    "battery_charging_voltage_c": SensorEntityDescription(
        key="battery_charging_voltage_c",
        name="Battery Charging Voltage C",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
    ),
    "battery_power_charge_total": SensorEntityDescription(
        key="battery_power_charge_total",
        name="Battery Power Charge Total",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    "battery_power_charge_a": SensorEntityDescription(
        key="battery_power_charge_a",
        name="Battery Power Charge A",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
    ),
    "battery_power_charge_b": SensorEntityDescription(
        key="battery_power_charge_b",
        name="Battery Power Charge B",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
    ),
    "battery_power_charge_c": SensorEntityDescription(
        key="battery_power_charge_c",
        name="Battery Power Charge C",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
    ),
    "battery_charge_total": SensorEntityDescription(
        key="battery_charge_total",
        name="Battery Charge Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
    ),
    "battery_charge_a": SensorEntityDescription(
        key="battery_charge_a",
        name="Battery Charge A",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        entity_registry_enabled_default=False,
    ),
    "battery_charge_b": SensorEntityDescription(
        key="battery_charge_b",
        name="Battery Charge B",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        entity_registry_enabled_default=False,
    ),
    "battery_charge_c": SensorEntityDescription(
        key="battery_charge_c",
        name="Battery Charge C",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        entity_registry_enabled_default=False,
    ),
    "battery_power_discharge_total": SensorEntityDescription(
        key="battery_power_discharge_total",
        name="Battery Power Discharge Total",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    "battery_power_discharge_a": SensorEntityDescription(
        key="battery_power_discharge_a",
        name="Battery Power Discharge A",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
    ),
    "battery_power_discharge_b": SensorEntityDescription(
        key="battery_power_discharge_b",
        name="Battery Power Discharge B",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
    ),
    "battery_power_discharge_c": SensorEntityDescription(
        key="battery_power_discharge_c",
        name="Battery Power Discharge C",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
    ),
    "battery_discharge_total": SensorEntityDescription(
        key="battery_discharge_total",
        name="Battery Discharge Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
    ),
    "battery_discharge_a": SensorEntityDescription(
        key="battery_discharge_a",
        name="Battery Discharge A",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        entity_registry_enabled_default=False,
    ),
    "battery_discharge_b": SensorEntityDescription(
        key="battery_discharge_b",
        name="Battery Discharge B",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        entity_registry_enabled_default=False,
    ),
    "battery_discharge_c": SensorEntityDescription(
        key="battery_discharge_c",
        name="Battery Discharge C",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        entity_registry_enabled_default=False,
    ),
    "inverter_power_limit": SensorEntityDescription(
        key="inverter_power_limit",
        name="Inverter Power Limit",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SMA sensors."""
    sma_data = hass.data[DOMAIN][config_entry.entry_id]

    coordinator = sma_data[PYSMA_COORDINATOR]
    used_sensors = sma_data[PYSMA_SENSORS]
    device_info = sma_data[PYSMA_DEVICE_INFO]

    if TYPE_CHECKING:
        assert config_entry.unique_id

    entities = []
    for sensor in used_sensors:
        entities.append(
            SMAsensor(
                coordinator,
                config_entry.unique_id,
                SENSOR_ENTITIES.get(sensor.name),
                device_info,
                sensor,
            )
        )

    async_add_entities(entities)


class SMAsensor(CoordinatorEntity, SensorEntity):
    """Representation of a SMA sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry_unique_id: str,
        description: SensorEntityDescription | None,
        device_info: DeviceInfo,
        pysma_sensor: pysma.sensor.Sensor,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        if description is not None:
            self.entity_description = description
        else:
            self._attr_name = pysma_sensor.name

        self._sensor = pysma_sensor

        self._attr_device_info = device_info
        self._attr_unique_id = (
            f"{config_entry_unique_id}-{pysma_sensor.key}_{pysma_sensor.key_idx}"
        )

        # Set sensor enabled to False.
        # Will be enabled by async_added_to_hass if actually used.
        self._sensor.enabled = False

    @property
    def name(self) -> str:
        """Return the name of the sensor prefixed with the device name."""
        if self._attr_device_info is None or not (
            name_prefix := self._attr_device_info.get("name")
        ):
            name_prefix = "SMA"

        return f"{name_prefix} {super().name}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._sensor.value

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self._sensor.enabled = True

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        self._sensor.enabled = False
