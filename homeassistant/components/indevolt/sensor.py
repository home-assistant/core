"""Sensor platform for Indevolt integration."""

from dataclasses import dataclass, field
from typing import Final

from indevolt_api import (
    IndevoltBattery,
    IndevoltConfig,
    IndevoltGrid,
    IndevoltSolar,
    IndevoltSystem,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IndevoltConfigEntry
from .coordinator import IndevoltCoordinator
from .entity import IndevoltEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class IndevoltSensorEntityDescription(SensorEntityDescription):
    """Custom entity description class for Indevolt sensors."""

    state_mapping: dict[str | int, str] = field(default_factory=dict)
    generation: list[int] = field(default_factory=lambda: [1, 2])


SENSORS: Final = (
    # System Operating Information
    IndevoltSensorEntityDescription(
        key=IndevoltSystem.OPERATING_MODE,
        translation_key="mode",
        state_mapping={"1000": "main", "1001": "sub", "1002": "standalone"},
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltConfig.READ_ENERGY_MODE,
        translation_key="energy_mode",
        state_mapping={
            0: "outdoor_portable",
            1: "self_consumed_prioritized",
            4: "real_time_control",
            5: "charge_discharge_schedule",
        },
        device_class=SensorDeviceClass.ENUM,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.RATED_CAPACITY_GEN2,
        generation=[2],
        translation_key="rated_capacity",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltConfig.READ_DISCHARGE_LIMIT,
        generation=[1],
        translation_key="discharge_limit",
        native_unit_of_measurement=PERCENTAGE,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltSystem.INPUT_POWER,
        translation_key="ac_input_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltSystem.OUTPUT_POWER,
        translation_key="ac_output_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltSystem.BYPASS_POWER,
        generation=[2],
        translation_key="bypass_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Electrical Energy Information
    IndevoltSensorEntityDescription(
        key=IndevoltSystem.TOTAL_INPUT_ENERGY,
        translation_key="total_ac_input_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltSystem.TOTAL_OUTPUT_ENERGY,
        generation=[2],
        translation_key="total_ac_output_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltSystem.OFF_GRID_OUTPUT_ENERGY,
        generation=[2],
        translation_key="off_grid_output_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltSystem.BYPASS_INPUT_ENERGY,
        generation=[2],
        translation_key="bypass_input_energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.DAILY_CHARGING_ENERGY,
        generation=[2],
        translation_key="battery_daily_charging_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.DAILY_DISCHARGING_ENERGY,
        generation=[2],
        translation_key="battery_daily_discharging_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.TOTAL_CHARGING_ENERGY,
        generation=[2],
        translation_key="battery_total_charging_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.TOTAL_DISCHARGING_ENERGY,
        generation=[2],
        translation_key="battery_total_discharging_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    # Electricity Meter Status
    IndevoltSensorEntityDescription(
        key=IndevoltGrid.METER_POWER_GEN2,
        generation=[2],
        translation_key="meter_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltGrid.METER_POWER_GEN1,
        generation=[1],
        translation_key="meter_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Grid information
    IndevoltSensorEntityDescription(
        key=IndevoltGrid.VOLTAGE,
        generation=[2],
        translation_key="grid_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltGrid.FREQUENCY,
        generation=[2],
        translation_key="grid_frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    # Battery Pack Operating Parameters
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.POWER,
        translation_key="battery_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.CHARGE_DISCHARGE_STATE,
        translation_key="battery_charge_discharge_state",
        state_mapping={1000: "static", 1001: "charging", 1002: "discharging"},
        device_class=SensorDeviceClass.ENUM,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.SOC,
        translation_key="battery_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # PV Operating Parameters
    IndevoltSensorEntityDescription(
        key=IndevoltSolar.DC_OUTPUT_POWER,
        translation_key="dc_output_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltSolar.DAILY_PRODUCTION,
        translation_key="daily_production",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltSolar.CUMULATIVE_PRODUCTION,
        translation_key="cumulative_production",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltSolar.DC_INPUT_CURRENT_1,
        generation=[2],
        translation_key="dc_input_current_1",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltSolar.DC_INPUT_VOLTAGE_1,
        generation=[2],
        translation_key="dc_input_voltage_1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltSolar.DC_INPUT_POWER_1,
        translation_key="dc_input_power_1",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltSolar.DC_INPUT_CURRENT_2,
        generation=[2],
        translation_key="dc_input_current_2",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltSolar.DC_INPUT_VOLTAGE_2,
        generation=[2],
        translation_key="dc_input_voltage_2",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltSolar.DC_INPUT_POWER_2,
        translation_key="dc_input_power_2",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltSolar.DC_INPUT_CURRENT_3,
        generation=[2],
        translation_key="dc_input_current_3",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltSolar.DC_INPUT_VOLTAGE_3,
        generation=[2],
        translation_key="dc_input_voltage_3",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltSolar.DC_INPUT_POWER_3,
        generation=[2],
        translation_key="dc_input_power_3",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltSolar.DC_INPUT_CURRENT_4,
        generation=[2],
        translation_key="dc_input_current_4",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltSolar.DC_INPUT_VOLTAGE_4,
        generation=[2],
        translation_key="dc_input_voltage_4",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltSolar.DC_INPUT_POWER_4,
        generation=[2],
        translation_key="dc_input_power_4",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    # Battery Pack Serial Numbers
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.MAIN_SERIAL_NUMBER,
        generation=[2],
        translation_key="main_serial_number",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.PACK_1_SERIAL_NUMBER,
        generation=[2],
        translation_key="battery_pack_1_serial_number",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.PACK_2_SERIAL_NUMBER,
        generation=[2],
        translation_key="battery_pack_2_serial_number",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.PACK_3_SERIAL_NUMBER,
        generation=[2],
        translation_key="battery_pack_3_serial_number",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.PACK_4_SERIAL_NUMBER,
        generation=[2],
        translation_key="battery_pack_4_serial_number",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.PACK_5_SERIAL_NUMBER,
        generation=[2],
        translation_key="battery_pack_5_serial_number",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # Battery Pack SOC
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.MAIN_SOC,
        generation=[2],
        translation_key="main_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.PACK_1_SOC,
        generation=[2],
        translation_key="battery_pack_1_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.PACK_2_SOC,
        generation=[2],
        translation_key="battery_pack_2_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.PACK_3_SOC,
        generation=[2],
        translation_key="battery_pack_3_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.PACK_4_SOC,
        generation=[2],
        translation_key="battery_pack_4_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.PACK_5_SOC,
        generation=[2],
        translation_key="battery_pack_5_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # Battery Pack Temperature
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.MAIN_TEMPERATURE,
        generation=[2],
        translation_key="main_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.PACK_1_TEMPERATURE,
        generation=[2],
        translation_key="battery_pack_1_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.PACK_2_TEMPERATURE,
        generation=[2],
        translation_key="battery_pack_2_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.PACK_3_TEMPERATURE,
        generation=[2],
        translation_key="battery_pack_3_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.PACK_4_TEMPERATURE,
        generation=[2],
        translation_key="battery_pack_4_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.PACK_5_TEMPERATURE,
        generation=[2],
        translation_key="battery_pack_5_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # Battery Pack Voltage
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.MAIN_VOLTAGE,
        generation=[2],
        translation_key="main_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.PACK_1_VOLTAGE,
        generation=[2],
        translation_key="battery_pack_1_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.PACK_2_VOLTAGE,
        generation=[2],
        translation_key="battery_pack_2_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.PACK_3_VOLTAGE,
        generation=[2],
        translation_key="battery_pack_3_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.PACK_4_VOLTAGE,
        generation=[2],
        translation_key="battery_pack_4_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.PACK_5_VOLTAGE,
        generation=[2],
        translation_key="battery_pack_5_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # Battery Pack Current
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.MAIN_CURRENT,
        generation=[2],
        translation_key="main_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.PACK_1_CURRENT,
        generation=[2],
        translation_key="battery_pack_1_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.PACK_2_CURRENT,
        generation=[2],
        translation_key="battery_pack_2_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.PACK_3_CURRENT,
        generation=[2],
        translation_key="battery_pack_3_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.PACK_4_CURRENT,
        generation=[2],
        translation_key="battery_pack_4_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltSensorEntityDescription(
        key=IndevoltBattery.PACK_5_CURRENT,
        generation=[2],
        translation_key="battery_pack_5_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)

# Sensors per battery pack (SN, SOC, Temperature, Voltage, Current)
BATTERY_PACK_SENSOR_KEYS = [
    (
        IndevoltBattery.PACK_1_SERIAL_NUMBER,
        IndevoltBattery.PACK_1_SOC,
        IndevoltBattery.PACK_1_TEMPERATURE,
        IndevoltBattery.PACK_1_VOLTAGE,
        IndevoltBattery.PACK_1_CURRENT,
    ),  # Battery Pack 1
    (
        IndevoltBattery.PACK_2_SERIAL_NUMBER,
        IndevoltBattery.PACK_2_SOC,
        IndevoltBattery.PACK_2_TEMPERATURE,
        IndevoltBattery.PACK_2_VOLTAGE,
        IndevoltBattery.PACK_2_CURRENT,
    ),  # Battery Pack 2
    (
        IndevoltBattery.PACK_3_SERIAL_NUMBER,
        IndevoltBattery.PACK_3_SOC,
        IndevoltBattery.PACK_3_TEMPERATURE,
        IndevoltBattery.PACK_3_VOLTAGE,
        IndevoltBattery.PACK_3_CURRENT,
    ),  # Battery Pack 3
    (
        IndevoltBattery.PACK_4_SERIAL_NUMBER,
        IndevoltBattery.PACK_4_SOC,
        IndevoltBattery.PACK_4_TEMPERATURE,
        IndevoltBattery.PACK_4_VOLTAGE,
        IndevoltBattery.PACK_4_CURRENT,
    ),  # Battery Pack 4
    (
        IndevoltBattery.PACK_5_SERIAL_NUMBER,
        IndevoltBattery.PACK_5_SOC,
        IndevoltBattery.PACK_5_TEMPERATURE,
        IndevoltBattery.PACK_5_VOLTAGE,
        IndevoltBattery.PACK_5_CURRENT,
    ),  # Battery Pack 5
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IndevoltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform for Indevolt."""
    coordinator = entry.runtime_data
    device_gen = coordinator.generation

    excluded_keys: set[str] = set()
    for pack_keys in BATTERY_PACK_SENSOR_KEYS:
        sn_key = pack_keys[0]

        if not coordinator.data.get(sn_key):
            excluded_keys.update(pack_keys)

    # Sensor initialization
    async_add_entities(
        IndevoltSensorEntity(coordinator, description)
        for description in SENSORS
        if device_gen in description.generation and description.key not in excluded_keys
    )


class IndevoltSensorEntity(IndevoltEntity, SensorEntity):
    """Represents a sensor entity for Indevolt devices."""

    entity_description: IndevoltSensorEntityDescription

    def __init__(
        self,
        coordinator: IndevoltCoordinator,
        description: IndevoltSensorEntityDescription,
    ) -> None:
        """Initialize the Indevolt sensor entity."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{self.serial_number}_{description.key}"

        # Sort options (prevent randomization) for ENUM values
        if description.device_class == SensorDeviceClass.ENUM:
            self._attr_options = sorted(set(description.state_mapping.values()))

    @property
    def native_value(self) -> str | int | float | None:
        """Return the current value of the sensor in its native unit."""
        raw_value = self.coordinator.data.get(self.entity_description.key)
        if raw_value is None:
            return None

        # Return descriptions for ENUM values
        if self.entity_description.device_class == SensorDeviceClass.ENUM:
            return self.entity_description.state_mapping.get(raw_value)

        return raw_value
