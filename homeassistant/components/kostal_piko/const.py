"""Constants for the Kostal Piko Solar Inverter integration."""

from pykostalpiko.dxs.current_values import (
    AnalogInputs,
    Battery,
    Grid,
    House,
    PVGenerator,
    S0Input,
)
from pykostalpiko.dxs.entry import Descriptor
from pykostalpiko.dxs.inverter import OPERATION_STATUS
from pykostalpiko.dxs.statistics import Day, Total

from homeassistant.components.sensor import (
    ATTR_LAST_RESET,
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    FREQUENCY_HERTZ,
    PERCENTAGE,
    POWER_WATT,
    TEMP_CELSIUS,
    TIME_HOURS,
    TIME_SECONDS,
)

DOMAIN = "kostal_piko"

LAST_RESET_DAILY = "daily"

# Available Sensors
#
# Each entry is defined with a tuple of these values:
#  - entry from the pykostalpiko library (Entries)
#  - sensor properties (dict)
SENSORS: list[tuple[Descriptor, dict]] = [
    (OPERATION_STATUS, {ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT}),
    (
        AnalogInputs.INPUT_1,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        AnalogInputs.INPUT_2,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        AnalogInputs.INPUT_3,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        AnalogInputs.INPUT_4,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Battery.VOLTAGE,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Battery.CHARGE,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.BATTERY,
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Battery.CURRENT,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.CURRENT,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (Battery.CYCLES, {ATTR_STATE_CLASS: SensorStateClass.TOTAL}),
    (
        Battery.TEMPERATURE,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
            ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Grid.Parameters.OUTPUT_POWER,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Grid.Parameters.FREQUENCY,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.FREQUENCY,
            ATTR_UNIT_OF_MEASUREMENT: FREQUENCY_HERTZ,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Grid.Parameters.POWER_FACTOR,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER_FACTOR,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Grid.Parameters.LIMITATION,
        {
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Grid.Phase1.VOLTAGE,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Grid.Phase1.CURRENT,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.CURRENT,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Grid.Phase1.POWER,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Grid.Phase2.VOLTAGE,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Grid.Phase2.CURRENT,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.CURRENT,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Grid.Phase2.POWER,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Grid.Phase3.VOLTAGE,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Grid.Phase3.CURRENT,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.CURRENT,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Grid.Phase3.POWER,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        House.CoveredBy.SOLAR_GENERATOR,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        House.CoveredBy.BATTERY,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        House.CoveredBy.GRID,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        House.PhaseConsumption.PHASE_1,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        House.PhaseConsumption.PHASE_2,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        House.PhaseConsumption.PHASE_3,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        PVGenerator.DcInput1.VOLTAGE,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        PVGenerator.DcInput1.CURRENT,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.CURRENT,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        PVGenerator.DcInput1.POWER,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        PVGenerator.DcInput2.VOLTAGE,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        PVGenerator.DcInput2.CURRENT,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.CURRENT,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        PVGenerator.DcInput2.POWER,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        PVGenerator.DcInput3.VOLTAGE,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        PVGenerator.DcInput3.CURRENT,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.CURRENT,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        PVGenerator.DcInput3.POWER,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        PVGenerator.CombinedInput.POWER,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        House.SELF_CONSUMPTION,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        S0Input.PULSE_COUNT,
        {
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        S0Input.PULSE_COUNT_TIMEFRAME,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.DURATION,
            ATTR_UNIT_OF_MEASUREMENT: TIME_SECONDS,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Day.YIELD,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_WATT_HOUR,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
            ATTR_LAST_RESET: LAST_RESET_DAILY,
        },
    ),
    (
        Day.HOME_CONSUMPTION,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_WATT_HOUR,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
            ATTR_LAST_RESET: LAST_RESET_DAILY,
        },
    ),
    (
        Day.SELF_CONSUMPTION,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_WATT_HOUR,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
            ATTR_LAST_RESET: LAST_RESET_DAILY,
        },
    ),
    (
        Day.SELF_CONSUMPTION_RATE,
        {
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
            ATTR_LAST_RESET: LAST_RESET_DAILY,
        },
    ),
    (
        Day.DEGREE_OF_SELF_SUFFICIENCY,
        {
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
            ATTR_LAST_RESET: LAST_RESET_DAILY,
        },
    ),
    (
        Total.YIELD,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
        },
    ),
    (
        Total.OPERATION_TIME,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.DURATION,
            ATTR_UNIT_OF_MEASUREMENT: TIME_HOURS,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
        },
    ),
    (
        Total.HOME_CONSUMPTION,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
        },
    ),
    (
        Total.SELF_CONSUMPTION,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
        },
    ),
    (
        Total.SELF_CONSUMPTION_RATE,
        {
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Total.DEGREE_OF_SELF_SUFFICIENCY,
        {
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
]


# This entry as a binary sensor
# (
#   Entries.BatteryCurrentDirection,
#   {
#     ATTR_DEVICE_CLASS: CHANGE_ME,
#     ATTR_UNIT_OF_MEASUREMENT: CHANGE_ME,
#     ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT
#   }
# ),
