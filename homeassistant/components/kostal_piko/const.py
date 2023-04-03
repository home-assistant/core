"""Constants for the Kostal Piko integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import kostal

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.helpers.typing import StateType

DOMAIN = "kostal_piko"

CONDITION_MAP_BATTERY_STATUS = {0: "charging", 1: "discharging"}

CONDITION_MAP_INVERTER_STATUS = {
    0: "unknown",
    1: "unknown",
    2: "starting",
    3: "feed_in",
}


def round_one(val: int):
    """Round the input value to one decimal."""
    return round(val, 1) if val is not None else val


def round_two(val: int):
    """Round the input value to two decimals."""
    return round(val, 2) if val is not None else val


@dataclass
class KostalPikoEntityDescription(SensorEntityDescription):
    """A class that describes piko sensor entities."""

    formatter: Callable[[Any], StateType] | None = None


# Defines all possible sensors
SENSOR_TYPES: tuple[KostalPikoEntityDescription, ...] = (
    # Analog Input sensors
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.VOLTAGE,
        key=str(kostal.ActualAnalogInputs.ANALOG1),
        name="Analog Input 1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.VOLTAGE,
        key=str(kostal.ActualAnalogInputs.ANALOG2),
        name="Analog Input 2",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.VOLTAGE,
        key=str(kostal.ActualAnalogInputs.ANALOG3),
        name="Analog Input 3",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.VOLTAGE,
        key=str(kostal.ActualAnalogInputs.ANALOG4),
        name="Analog Input 4",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    # Battery sensors
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.VOLTAGE,
        key=str(kostal.ActualBattery.VOLTAGE),
        name="Battery Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.BATTERY,
        key=str(kostal.ActualBattery.CHARGE),
        name="Battery Charge",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.CURRENT,
        key=str(kostal.ActualBattery.CURRENT),
        name="Battery Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        key=str(kostal.ActualBattery.CURRENT_DIR),
        name="Battery Charging State",
        icon="mdi:plus-minus",
        translation_key="kostal_piko_battery_charging_state",
        formatter=lambda b: CONDITION_MAP_BATTERY_STATUS[b]
        if b in CONDITION_MAP_BATTERY_STATUS
        else b,
    ),
    KostalPikoEntityDescription(
        key=str(kostal.ActualBattery.CHARGE_CYCLES),
        name="Battery Charge Cycles",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:tally-mark-5",
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        key=str(kostal.ActualBattery.TEMPERATURE),
        name="Battery Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    # Grid sensors
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.POWER,
        key=str(kostal.ActualGrid.GRID_OUTPUT_POWER),
        name="Output Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.FREQUENCY,
        key=str(kostal.ActualGrid.GRID_FREQ),
        name="Grid Frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.POWER_FACTOR,
        key=str(kostal.ActualGrid.GRID_COS_PHI),
        name="Power Factor",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=lambda p: round(p * 100, 2),
    ),
    KostalPikoEntityDescription(
        key=str(kostal.ActualGrid.GRID_LIMITATION),
        name="Limitation",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:car-speed-limiter",
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.VOLTAGE,
        key=str(kostal.ActualGrid.GRID_VOLTAGE_L1),
        name="Voltage L1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.CURRENT,
        key=str(kostal.ActualGrid.GRID_CURRENT_L1),
        name="Current L1",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.POWER,
        key=str(kostal.ActualGrid.GRID_POWER_L1),
        name="Power L1",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.VOLTAGE,
        key=str(kostal.ActualGrid.GRID_VOLTAGE_L2),
        name="Voltage L2",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.CURRENT,
        key=str(kostal.ActualGrid.GRID_CURRENT_L2),
        name="Current L2",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.POWER,
        key=str(kostal.ActualGrid.GRID_POWER_L2),
        name="Power L2",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.VOLTAGE,
        key=str(kostal.ActualGrid.GRID_VOLTAGE_L3),
        name="Voltage L3",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.CURRENT,
        key=str(kostal.ActualGrid.GRID_CURRENT_L3),
        name="Current L3",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.POWER,
        key=str(kostal.ActualGrid.GRID_POWER_L3),
        name="Power L3",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    # Home sensors
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.POWER,
        key=str(kostal.ActualHome.ACT_HOME_CONSUMPTION_SOLAR),
        name="Home Consumption from Solar",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.POWER,
        key=str(kostal.ActualHome.ACT_HOME_CONSUMPTION_BATTERY),
        name="Home Consumption from Battery",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.POWER,
        key=str(kostal.ActualHome.ACT_HOME_CONSUMPTION_GRID),
        name="Home Consumption from Grid",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.POWER,
        key=str(kostal.ActualHome.PHASE_SELECTIVE_CONSUMPTION_L1),
        name="Home Consumption L1",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.POWER,
        key=str(kostal.ActualHome.PHASE_SELECTIVE_CONSUMPTION_L2),
        name="Home Consumption L2",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.POWER,
        key=str(kostal.ActualHome.PHASE_SELECTIVE_CONSUMPTION_L3),
        name="Home Consumption L3",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.POWER,
        key=str(kostal.Home.DC_POWER_PV),
        name="DC Power PV",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.POWER,
        key=str(kostal.Home.OWN_CONSUMPTION),
        name="Self Consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        key=str(kostal.Home.OPERATING_STATUS),
        name="Operating Status",
        icon="mdi:state-machine",
        translation_key="kostal_piko_inverter_operating_state",
        formatter=lambda s: CONDITION_MAP_INVERTER_STATUS[s]
        if s in CONDITION_MAP_INVERTER_STATUS
        else s,
    ),
    # PVGenerator sensors
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.VOLTAGE,
        key=str(kostal.ActualGenerator.DC_1_VOLTAGE),
        name="DC 1 Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.CURRENT,
        key=str(kostal.ActualGenerator.DC_1_CURRENT),
        name="DC 1 Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.POWER,
        key=str(kostal.ActualGenerator.DC_1_POWER),
        name="DC 1 Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.VOLTAGE,
        key=str(kostal.ActualGenerator.DC_2_VOLTAGE),
        name="DC 2 Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.CURRENT,
        key=str(kostal.ActualGenerator.DC_2_CURRENT),
        name="DC 2 Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.POWER,
        key=str(kostal.ActualGenerator.DC_2_POWER),
        name="DC 2 Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.VOLTAGE,
        key=str(kostal.ActualGenerator.DC_3_VOLTAGE),
        name="DC 3 Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.CURRENT,
        key=str(kostal.ActualGenerator.DC_3_CURRENT),
        name="DC 3 Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.POWER,
        key=str(kostal.ActualGenerator.DC_3_POWER),
        name="DC 3 Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter=round_one,
    ),
    # S0 sensors
    KostalPikoEntityDescription(
        key=str(kostal.ActualSZeroIn.S0_IN_PULSE_COUNT),
        name="S0 in Pulses",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:pulse",
    ),
    KostalPikoEntityDescription(
        key=str(kostal.ActualSZeroIn.LOG_INTERVAL),
        name="Log Interval",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:timer",
    ),
    # Daily statistics sensors
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.ENERGY,
        key=str(kostal.StatisticDay.YIELD),
        name="Daily Yield",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.ENERGY,
        key=str(kostal.StatisticDay.HOME_CONSUMPTION),
        name="Daily Home Consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.ENERGY,
        key=str(kostal.StatisticDay.SELF_CONSUMPTION),
        name="Daily Self Consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        key=str(kostal.StatisticDay.SELF_CONSUMPTION_RATE),
        name="Daily Self Consumption Rate",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:chart-donut",
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        key=str(kostal.StatisticDay.AUTONOMY_DEGREE),
        name="Daily Autonomy Degree",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:transmission-tower-off",
        formatter=round_one,
    ),
    # Total statistics sensors
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.ENERGY,
        key=str(kostal.StatisticTotal.YIELD),
        name="Total Yield",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter=round_two,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.DURATION,
        key=str(kostal.StatisticTotal.OPERATING_TIME),
        name="Total Operating Time",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.ENERGY,
        key=str(kostal.StatisticTotal.HOME_CONSUMPTION),
        name="Total Home Consumption",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter=round_two,
    ),
    KostalPikoEntityDescription(
        device_class=SensorDeviceClass.ENERGY,
        key=str(kostal.StatisticTotal.SELF_CONSUMPTION),
        name="Total Self Consumption",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter=round_two,
    ),
    KostalPikoEntityDescription(
        key=str(kostal.StatisticTotal.SELF_CONSUMPTION_RATE),
        name="Total Self Consumption Rate",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:chart-donut",
        formatter=round_one,
    ),
    KostalPikoEntityDescription(
        key=str(kostal.StatisticTotal.AUTONOMY_DEGREE),
        name="Total Autonomy Degree",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:transmission-tower-off",
        formatter=round_one,
    ),
)
