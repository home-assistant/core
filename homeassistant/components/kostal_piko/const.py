"""Constants for the Kostal Piko Solar Inverter integration."""

from pykostalpiko.dxs import Entries

from homeassistant.components.sensor import (
    ATTR_LAST_RESET,
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ENTITY_CATEGORY,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    FREQUENCY_HERTZ,
    PERCENTAGE,
    POWER_WATT,
    TEMP_CELSIUS,
)
from homeassistant.helpers.entity import EntityCategory

DOMAIN = "kostal_piko"

LAST_RESET_DAILY = "daily"

# Available Sensors
#
# Each entry is defined with a tuple of these values:
#  - entry from the pykostalpiko library (Entries)
#  - sensor properties (dict)
SENSORS: list[tuple[Entries, dict]] = [
    (
        Entries.AnalaogInput1,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.AnalaogInput2,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.AnalaogInput3,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.AnalaogInput4,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.BatteryVoltage,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.BatteryCharge,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.BATTERY,
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.BatteryCurrent,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.CURRENT,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (Entries.BatteryChargeCycles, {ATTR_STATE_CLASS: SensorStateClass.TOTAL}),
    (
        Entries.BatteryTemperature,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
            ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.GridOutputPower,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.GridFrequency,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.FREQUENCY,
            ATTR_UNIT_OF_MEASUREMENT: FREQUENCY_HERTZ,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.GridLimitation,
        {
            # ATTR_DEVICE_CLASS: CHANGE_ME,
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.GridVoltageL1,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.GridCurrentL1,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.CURRENT,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.GridPowerL1,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.GridVoltageL2,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.GridCurrentL2,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.CURRENT,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.GridPowerL2,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.GridVoltageL3,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.GridCurrentL3,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.CURRENT,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.GridPowerL3,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.HomeConsumptionSolar,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.HomeConsumptionBattery,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.HomeConsumptionGrid,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.HomeConsumptionL1,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.HomeConsumptionL2,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.HomeConsumptionL3,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.GeneratorDc1Voltage,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.GeneratorDc1Current,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.CURRENT,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.GeneratorDc1Power,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.GeneratorDc2Voltage,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.GeneratorDc2Current,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.CURRENT,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.GeneratorDc2Power,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.GeneratorDc3Voltage,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.GeneratorDc3Current,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.CURRENT,
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.GeneratorDc3Power,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.HomeDcPowerPV,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.HomeOwnConsumption,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    ),
    (
        Entries.InverterName,
        {
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
            CONF_ENTITY_CATEGORY: EntityCategory.DIAGNOSTIC,
        },
    ),
    (
        Entries.InverterType,
        {
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
            CONF_ENTITY_CATEGORY: EntityCategory.DIAGNOSTIC,
        },
    ),
    (
        Entries.VersionUI,
        {
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
            CONF_ENTITY_CATEGORY: EntityCategory.DIAGNOSTIC,
        },
    ),
    (
        Entries.VersionFW,
        {
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
            CONF_ENTITY_CATEGORY: EntityCategory.DIAGNOSTIC,
        },
    ),
    (
        Entries.VersionHW,
        {
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
            CONF_ENTITY_CATEGORY: EntityCategory.DIAGNOSTIC,
        },
    ),
    (
        Entries.VersionPAR,
        {
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
            CONF_ENTITY_CATEGORY: EntityCategory.DIAGNOSTIC,
        },
    ),
    (
        Entries.SerialNumber,
        {
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
            CONF_ENTITY_CATEGORY: EntityCategory.DIAGNOSTIC,
        },
    ),
    (
        Entries.ArticleNumber,
        {
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
            CONF_ENTITY_CATEGORY: EntityCategory.DIAGNOSTIC,
        },
    ),
    (
        Entries.CountrySettingsName,
        {
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
            CONF_ENTITY_CATEGORY: EntityCategory.DIAGNOSTIC,
        },
    ),
    (
        Entries.CountrySettingsVersion,
        {
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
            CONF_ENTITY_CATEGORY: EntityCategory.DIAGNOSTIC,
        },
    ),
    (
        Entries.StatisticsDayYield,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_WATT_HOUR,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
            ATTR_LAST_RESET: LAST_RESET_DAILY,
        },
    ),
    (
        Entries.StatisticsDayHomeConsumption,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_WATT_HOUR,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
            ATTR_LAST_RESET: LAST_RESET_DAILY,
        },
    ),
    (
        Entries.StatisticsDayOwnConsumption,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_WATT_HOUR,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
            ATTR_LAST_RESET: LAST_RESET_DAILY,
        },
    ),
    (
        Entries.StatisticsDayOwnConsumptionRate,
        {
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
            ATTR_LAST_RESET: LAST_RESET_DAILY,
        },
    ),
    (
        Entries.StatisticsDayAutonomyDegree,
        {
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
            ATTR_LAST_RESET: LAST_RESET_DAILY,
        },
    ),
    (
        Entries.StatisticsTotalYield,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_WATT_HOUR,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
        },
    ),
    (
        Entries.StatisticsTotalOperatingTime,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
        },
    ),
    (
        Entries.StatisticsTotalHomeConsumption,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
        },
    ),
    (
        Entries.StatisticsTotalOwnConsumption,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
        },
    ),
    (
        Entries.StatisticsTotalOwnConsRate,
        {
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
        },
    ),
    (
        Entries.StatisticsTotalAutonomyDegree,
        {
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL,
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

# This value should be mapped somehow
# 0 - Off
# 1 - Idle
# 2 - Starting
# 3 - Feed MPP
# 4 - Deactivated
# 5 - Feed
# (
#   Entries.HomeOperatingStatus,
#   {
#     ATTR_DEVICE_CLASS: CHANGE_ME,
#     ATTR_UNIT_OF_MEASUREMENT: CHANGE_ME,
#     ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT
#   }
# ),
# I dont know what these do
# (
#   Entries.S0InPulseCnt,
#   {
#     ATTR_DEVICE_CLASS: CHANGE_ME,
#     ATTR_UNIT_OF_MEASUREMENT: CHANGE_ME,
#     ATTR_STATE_CLASS: CHANGE_ME
#   }
# ),
# (
#   Entries.S0InLoginterval,
#   {
#     ATTR_DEVICE_CLASS: CHANGE_ME,
#     ATTR_UNIT_OF_MEASUREMENT: CHANGE_ME,
#     ATTR_STATE_CLASS: CHANGE_ME
#   }
# ),
# I have no clue what this measures
# (
#   Entries.GridCosPhi,
#   {
#     ATTR_DEVICE_CLASS: CHANGE_ME,
#     ATTR_UNIT_OF_MEASUREMENT: CHANGE_ME,
#     ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT
#   }
# ),
