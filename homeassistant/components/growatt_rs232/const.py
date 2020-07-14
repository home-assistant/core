"""Constants for Growatt RS232 integration."""

from growattRS232.const import (
    ATTR_DERATING,
    ATTR_DERATING_MODE,
    ATTR_FAULT,
    ATTR_FAULT_CODE,
    ATTR_FREQUENCY,
    ATTR_INPUT_1_AMPERAGE,
    ATTR_INPUT_1_ENERGY_TODAY,
    ATTR_INPUT_1_ENERGY_TOTAL,
    ATTR_INPUT_1_POWER,
    ATTR_INPUT_1_VOLTAGE,
    ATTR_INPUT_2_AMPERAGE,
    ATTR_INPUT_2_ENERGY_TODAY,
    ATTR_INPUT_2_ENERGY_TOTAL,
    ATTR_INPUT_2_POWER,
    ATTR_INPUT_2_VOLTAGE,
    ATTR_INPUT_ENERGY_TOTAL,
    ATTR_INPUT_POWER,
    ATTR_IPM_TEMPERATURE,
    ATTR_N_BUS_VOLTAGE,
    ATTR_OPERATION_HOURS,
    ATTR_OUTPUT_1_AMPERAGE,
    ATTR_OUTPUT_1_POWER,
    ATTR_OUTPUT_1_VOLTAGE,
    ATTR_OUTPUT_2_AMPERAGE,
    ATTR_OUTPUT_2_POWER,
    ATTR_OUTPUT_2_VOLTAGE,
    ATTR_OUTPUT_3_AMPERAGE,
    ATTR_OUTPUT_3_POWER,
    ATTR_OUTPUT_3_VOLTAGE,
    ATTR_OUTPUT_ENERGY_TODAY,
    ATTR_OUTPUT_ENERGY_TOTAL,
    ATTR_OUTPUT_POWER,
    ATTR_OUTPUT_REACTIVE_ENERGY_TODAY,
    ATTR_OUTPUT_REACTIVE_ENERGY_TOTAL,
    ATTR_OUTPUT_REACTIVE_POWER,
    ATTR_P_BUS_VOLTAGE,
    ATTR_STATUS,
    ATTR_STATUS_CODE,
    ATTR_TEMPERATURE,
    ATTR_WARNING,
    ATTR_WARNING_CODE,
    ATTR_WARNING_VALUE,
)

from homeassistant.const import (
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    ELECTRICAL_CURRENT_AMPERE,
    ENERGY_KILO_WATT_HOUR,
    FREQUENCY_HERTZ,
    POWER_WATT,
    TEMP_CELSIUS,
    TIME_HOURS,
    VOLT,
)

# Base component constants
NAME = "Growatt RS232"
DOMAIN = "growatt_rs232"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "1.0.0"

ISSUE_URL = "https://github.com/home-assistant/core/issues"

STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
Domain: {DOMAIN}
Version: {VERSION}
This is a Home Assistant integration.
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""

# Platforms
SENSOR = "sensor"
PLATFORMS = [SENSOR]

# Icons
ICON = "mdi:WhiteBalanceSunny"
ICON_INPUT = "mdi:Import"
ICON_OUTPUT = "mdiExport"

# Attributes
ATTR_LABEL = "label"

SENSOR_TYPES = {
    ATTR_STATUS: {
        ATTR_ICON: ICON,
        ATTR_LABEL: ATTR_STATUS.title(),
        ATTR_UNIT_OF_MEASUREMENT: None,
    },
    ATTR_STATUS_CODE: {
        ATTR_ICON: ICON,
        ATTR_LABEL: ATTR_STATUS_CODE.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: None,
    },
    ATTR_INPUT_POWER: {
        ATTR_ICON: ICON_INPUT,
        ATTR_LABEL: ATTR_INPUT_POWER.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
    },
    ATTR_INPUT_ENERGY_TOTAL: {
        ATTR_ICON: ICON_INPUT,
        ATTR_LABEL: ATTR_INPUT_ENERGY_TOTAL.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
    },
    ATTR_INPUT_1_AMPERAGE: {
        ATTR_ICON: ICON_INPUT,
        ATTR_LABEL: ATTR_INPUT_1_AMPERAGE.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: ELECTRICAL_CURRENT_AMPERE,
    },
    ATTR_INPUT_1_VOLTAGE: {
        ATTR_ICON: ICON_INPUT,
        ATTR_LABEL: ATTR_INPUT_1_VOLTAGE.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: VOLT,
    },
    ATTR_INPUT_1_POWER: {
        ATTR_ICON: ICON_INPUT,
        ATTR_LABEL: ATTR_INPUT_1_POWER.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
    },
    ATTR_INPUT_1_ENERGY_TODAY: {
        ATTR_ICON: ICON_INPUT,
        ATTR_LABEL: ATTR_INPUT_1_ENERGY_TODAY.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
    },
    ATTR_INPUT_1_ENERGY_TOTAL: {
        ATTR_ICON: ICON_INPUT,
        ATTR_LABEL: ATTR_INPUT_1_ENERGY_TOTAL.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
    },
    ATTR_INPUT_2_AMPERAGE: {
        ATTR_ICON: ICON_INPUT,
        ATTR_LABEL: ATTR_INPUT_2_AMPERAGE.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: ELECTRICAL_CURRENT_AMPERE,
    },
    ATTR_INPUT_2_VOLTAGE: {
        ATTR_ICON: ICON_INPUT,
        ATTR_LABEL: ATTR_INPUT_2_VOLTAGE.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: VOLT,
    },
    ATTR_INPUT_2_POWER: {
        ATTR_ICON: ICON_INPUT,
        ATTR_LABEL: ATTR_INPUT_2_POWER.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
    },
    ATTR_INPUT_2_ENERGY_TODAY: {
        ATTR_ICON: ICON_INPUT,
        ATTR_LABEL: ATTR_INPUT_2_ENERGY_TODAY.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
    },
    ATTR_INPUT_2_ENERGY_TOTAL: {
        ATTR_ICON: ICON_INPUT,
        ATTR_LABEL: ATTR_INPUT_2_ENERGY_TOTAL.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
    },
    ATTR_OUTPUT_POWER: {
        ATTR_ICON: ICON_OUTPUT,
        ATTR_LABEL: ATTR_OUTPUT_POWER.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
    },
    ATTR_OUTPUT_ENERGY_TODAY: {
        ATTR_ICON: ICON_OUTPUT,
        ATTR_LABEL: ATTR_OUTPUT_ENERGY_TODAY.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
    },
    ATTR_OUTPUT_ENERGY_TOTAL: {
        ATTR_ICON: ICON_OUTPUT,
        ATTR_LABEL: ATTR_OUTPUT_ENERGY_TOTAL.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
    },
    ATTR_OUTPUT_REACTIVE_POWER: {
        ATTR_ICON: ICON_OUTPUT,
        ATTR_LABEL: ATTR_OUTPUT_REACTIVE_POWER.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
    },
    ATTR_OUTPUT_REACTIVE_ENERGY_TODAY: {
        ATTR_ICON: ICON_OUTPUT,
        ATTR_LABEL: ATTR_OUTPUT_REACTIVE_ENERGY_TODAY.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
    },
    ATTR_OUTPUT_REACTIVE_ENERGY_TOTAL: {
        ATTR_ICON: ICON_OUTPUT,
        ATTR_LABEL: ATTR_OUTPUT_REACTIVE_ENERGY_TOTAL.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
    },
    ATTR_OUTPUT_1_VOLTAGE: {
        ATTR_ICON: ICON_OUTPUT,
        ATTR_LABEL: ATTR_OUTPUT_1_VOLTAGE.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: VOLT,
    },
    ATTR_OUTPUT_1_AMPERAGE: {
        ATTR_ICON: ICON_OUTPUT,
        ATTR_LABEL: ATTR_OUTPUT_1_AMPERAGE.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: ELECTRICAL_CURRENT_AMPERE,
    },
    ATTR_OUTPUT_1_POWER: {
        ATTR_ICON: ICON_OUTPUT,
        ATTR_LABEL: ATTR_OUTPUT_1_POWER.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
    },
    ATTR_OUTPUT_2_VOLTAGE: {
        ATTR_ICON: ICON_OUTPUT,
        ATTR_LABEL: ATTR_OUTPUT_2_VOLTAGE.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: VOLT,
    },
    ATTR_OUTPUT_2_AMPERAGE: {
        ATTR_ICON: ICON_OUTPUT,
        ATTR_LABEL: ATTR_OUTPUT_2_AMPERAGE.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: ELECTRICAL_CURRENT_AMPERE,
    },
    ATTR_OUTPUT_2_POWER: {
        ATTR_ICON: ICON_OUTPUT,
        ATTR_LABEL: ATTR_OUTPUT_2_POWER.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
    },
    ATTR_OUTPUT_3_VOLTAGE: {
        ATTR_ICON: ICON_OUTPUT,
        ATTR_LABEL: ATTR_OUTPUT_3_VOLTAGE.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: VOLT,
    },
    ATTR_OUTPUT_3_AMPERAGE: {
        ATTR_ICON: ICON_OUTPUT,
        ATTR_LABEL: ATTR_OUTPUT_3_AMPERAGE.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: ELECTRICAL_CURRENT_AMPERE,
    },
    ATTR_OUTPUT_3_POWER: {
        ATTR_ICON: ICON_OUTPUT,
        ATTR_LABEL: ATTR_OUTPUT_3_POWER.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
    },
    ATTR_OPERATION_HOURS: {
        ATTR_ICON: ICON,
        ATTR_LABEL: ATTR_OPERATION_HOURS.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: TIME_HOURS,
    },
    ATTR_FREQUENCY: {
        ATTR_ICON: ICON,
        ATTR_LABEL: ATTR_FREQUENCY.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: FREQUENCY_HERTZ,
    },
    ATTR_TEMPERATURE: {
        ATTR_ICON: ICON_OUTPUT,
        ATTR_LABEL: ATTR_TEMPERATURE.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
    },
    ATTR_IPM_TEMPERATURE: {
        ATTR_ICON: ICON,
        ATTR_LABEL: ATTR_IPM_TEMPERATURE.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
    },
    ATTR_P_BUS_VOLTAGE: {
        ATTR_ICON: ICON,
        ATTR_LABEL: ATTR_P_BUS_VOLTAGE.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: VOLT,
    },
    ATTR_N_BUS_VOLTAGE: {
        ATTR_ICON: ICON,
        ATTR_LABEL: ATTR_N_BUS_VOLTAGE.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: VOLT,
    },
    ATTR_DERATING_MODE: {
        ATTR_ICON: ICON,
        ATTR_LABEL: ATTR_DERATING_MODE.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: None,
    },
    ATTR_DERATING: {
        ATTR_ICON: ICON,
        ATTR_LABEL: ATTR_DERATING.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: None,
    },
    ATTR_FAULT_CODE: {
        ATTR_ICON: ICON,
        ATTR_LABEL: ATTR_FAULT_CODE.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: None,
    },
    ATTR_FAULT: {
        ATTR_ICON: ICON,
        ATTR_LABEL: ATTR_FAULT.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: None,
    },
    ATTR_WARNING_CODE: {
        ATTR_ICON: ICON,
        ATTR_LABEL: ATTR_WARNING_CODE.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: None,
    },
    ATTR_WARNING_VALUE: {
        ATTR_ICON: ICON,
        ATTR_LABEL: ATTR_WARNING_VALUE.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: None,
    },
    ATTR_WARNING: {
        ATTR_ICON: ICON,
        ATTR_LABEL: ATTR_WARNING.replace("_", " ").title(),
        ATTR_UNIT_OF_MEASUREMENT: None,
    },
}
