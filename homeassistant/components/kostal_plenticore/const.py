"""Constants for the Kostal Plenticore Solar Inverter integration."""
from dataclasses import dataclass
from typing import NamedTuple

from homeassistant.components.number import NumberEntityDescription
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
)
from homeassistant.helpers.entity import EntityCategory

DOMAIN = "kostal_plenticore"

ATTR_ENABLED_DEFAULT = "entity_registry_enabled_default"

# Defines all entities for process data.
#
# Each entry is defined with a tuple of these values:
#  - module id (str)
#  - process data id (str)
#  - entity name suffix (str)
#  - sensor properties (dict)
#  - value formatter (str)
SENSOR_PROCESS_DATA = [
    (
        "devices:local",
        "Inverter:State",
        "Inverter State",
        {ATTR_ICON: "mdi:state-machine"},
        "format_inverter_state",
    ),
    (
        "devices:local",
        "Dc_P",
        "Solar Power",
        {
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_ENABLED_DEFAULT: True,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        "format_round",
    ),
    (
        "devices:local",
        "Grid_P",
        "Grid Power",
        {
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_ENABLED_DEFAULT: True,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        "format_round",
    ),
    (
        "devices:local",
        "HomeBat_P",
        "Home Power from Battery",
        {
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
        },
        "format_round",
    ),
    (
        "devices:local",
        "HomeGrid_P",
        "Home Power from Grid",
        {
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        "format_round",
    ),
    (
        "devices:local",
        "HomeOwn_P",
        "Home Power from Own",
        {
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        "format_round",
    ),
    (
        "devices:local",
        "HomePv_P",
        "Home Power from PV",
        {
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        "format_round",
    ),
    (
        "devices:local",
        "Home_P",
        "Home Power",
        {
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        "format_round",
    ),
    (
        "devices:local:ac",
        "P",
        "AC Power",
        {
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_ENABLED_DEFAULT: True,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        "format_round",
    ),
    (
        "devices:local:pv1",
        "P",
        "DC1 Power",
        {
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        "format_round",
    ),
    (
        "devices:local:pv1",
        "U",
        "DC1 Voltage",
        {
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        "format_round",
    ),
    (
        "devices:local:pv1",
        "I",
        "DC1 Current",
        {
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
            ATTR_DEVICE_CLASS: SensorDeviceClass.CURRENT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        "format_float",
    ),
    (
        "devices:local:pv2",
        "P",
        "DC2 Power",
        {
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        "format_round",
    ),
    (
        "devices:local:pv2",
        "U",
        "DC2 Voltage",
        {
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        "format_round",
    ),
    (
        "devices:local:pv2",
        "I",
        "DC2 Current",
        {
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
            ATTR_DEVICE_CLASS: SensorDeviceClass.CURRENT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        "format_float",
    ),
    (
        "devices:local:pv3",
        "P",
        "DC3 Power",
        {
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        "format_round",
    ),
    (
        "devices:local:pv3",
        "U",
        "DC3 Voltage",
        {
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        "format_round",
    ),
    (
        "devices:local:pv3",
        "I",
        "DC3 Current",
        {
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
            ATTR_DEVICE_CLASS: SensorDeviceClass.CURRENT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        "format_float",
    ),
    (
        "devices:local",
        "PV2Bat_P",
        "PV to Battery Power",
        {
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        "format_round",
    ),
    (
        "devices:local",
        "EM_State",
        "Energy Manager State",
        {ATTR_ICON: "mdi:state-machine"},
        "format_em_manager_state",
    ),
    (
        "devices:local:battery",
        "Cycles",
        "Battery Cycles",
        {ATTR_ICON: "mdi:recycle", ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT},
        "format_round",
    ),
    (
        "devices:local:battery",
        "P",
        "Battery Power",
        {
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        "format_round",
    ),
    (
        "devices:local:battery",
        "SoC",
        "Battery SoC",
        {
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            ATTR_DEVICE_CLASS: SensorDeviceClass.BATTERY,
        },
        "format_round",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:Autarky:Day",
        "Autarky Day",
        {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE, ATTR_ICON: "mdi:chart-donut"},
        "format_round",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:Autarky:Month",
        "Autarky Month",
        {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE, ATTR_ICON: "mdi:chart-donut"},
        "format_round",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:Autarky:Total",
        "Autarky Total",
        {
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            ATTR_ICON: "mdi:chart-donut",
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        "format_round",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:Autarky:Year",
        "Autarky Year",
        {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE, ATTR_ICON: "mdi:chart-donut"},
        "format_round",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:OwnConsumptionRate:Day",
        "Own Consumption Rate Day",
        {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE, ATTR_ICON: "mdi:chart-donut"},
        "format_round",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:OwnConsumptionRate:Month",
        "Own Consumption Rate Month",
        {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE, ATTR_ICON: "mdi:chart-donut"},
        "format_round",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:OwnConsumptionRate:Total",
        "Own Consumption Rate Total",
        {
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            ATTR_ICON: "mdi:chart-donut",
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        "format_round",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:OwnConsumptionRate:Year",
        "Own Consumption Rate Year",
        {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE, ATTR_ICON: "mdi:chart-donut"},
        "format_round",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHome:Day",
        "Home Consumption Day",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHome:Month",
        "Home Consumption Month",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHome:Year",
        "Home Consumption Year",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHome:Total",
        "Home Consumption Total",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHomeBat:Day",
        "Home Consumption from Battery Day",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHomeBat:Month",
        "Home Consumption from Battery Month",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHomeBat:Year",
        "Home Consumption from Battery Year",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHomeBat:Total",
        "Home Consumption from Battery Total",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHomeGrid:Day",
        "Home Consumption from Grid Day",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHomeGrid:Month",
        "Home Consumption from Grid Month",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHomeGrid:Year",
        "Home Consumption from Grid Year",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHomeGrid:Total",
        "Home Consumption from Grid Total",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHomePv:Day",
        "Home Consumption from PV Day",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHomePv:Month",
        "Home Consumption from PV Month",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHomePv:Year",
        "Home Consumption from PV Year",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHomePv:Total",
        "Home Consumption from PV Total",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyPv1:Day",
        "Energy PV1 Day",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyPv1:Month",
        "Energy PV1 Month",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyPv1:Year",
        "Energy PV1 Year",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyPv1:Total",
        "Energy PV1 Total",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyPv2:Day",
        "Energy PV2 Day",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyPv2:Month",
        "Energy PV2 Month",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyPv2:Year",
        "Energy PV2 Year",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyPv2:Total",
        "Energy PV2 Total",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyPv3:Day",
        "Energy PV3 Day",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyPv3:Month",
        "Energy PV3 Month",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyPv3:Year",
        "Energy PV3 Year",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyPv3:Total",
        "Energy PV3 Total",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:Yield:Day",
        "Energy Yield Day",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_ENABLED_DEFAULT: True,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:Yield:Month",
        "Energy Yield Month",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:Yield:Year",
        "Energy Yield Year",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:Yield:Total",
        "Energy Yield Total",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyChargeGrid:Day",
        "Battery Charge from Grid Day",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyChargeGrid:Month",
        "Battery Charge from Grid Month",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyChargeGrid:Year",
        "Battery Charge from Grid Year",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyChargeGrid:Total",
        "Battery Charge from Grid Total",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyChargePv:Day",
        "Battery Charge from PV Day",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyChargePv:Month",
        "Battery Charge from PV Month",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyChargePv:Year",
        "Battery Charge from PV Year",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyChargePv:Total",
        "Battery Charge from PV Total",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyDischargeGrid:Day",
        "Energy Discharge to Grid Day",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyDischargeGrid:Month",
        "Energy Discharge to Grid Month",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyDischargeGrid:Year",
        "Energy Discharge to Grid Year",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyDischargeGrid:Total",
        "Energy Discharge to Grid Total",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
        "format_energy",
    ),
]


@dataclass
class PlenticoreNumberEntityDescriptionMixin:
    """Define an entity description mixin for number entities."""

    module_id: str
    data_id: str
    fmt_from: str
    fmt_to: str


@dataclass
class PlenticoreNumberEntityDescription(
    NumberEntityDescription, PlenticoreNumberEntityDescriptionMixin
):
    """Describes a Plenticore number entity."""


NUMBER_SETTINGS_DATA = [
    PlenticoreNumberEntityDescription(
        key="battery_min_soc",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:battery-negative",
        name="Battery min SoC",
        native_unit_of_measurement=PERCENTAGE,
        native_max_value=100,
        native_min_value=5,
        native_step=5,
        module_id="devices:local",
        data_id="Battery:MinSoc",
        fmt_from="format_round",
        fmt_to="format_round_back",
    ),
    PlenticoreNumberEntityDescription(
        key="battery_min_home_consumption",
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        name="Battery min Home Consumption",
        native_unit_of_measurement=POWER_WATT,
        native_max_value=38000,
        native_min_value=50,
        native_step=1,
        module_id="devices:local",
        data_id="Battery:MinHomeComsumption",
        fmt_from="format_round",
        fmt_to="format_round_back",
    ),
]


class SwitchData(NamedTuple):
    """Representation of a SelectData tuple."""

    module_id: str
    data_id: str
    name: str
    is_on: str
    on_value: str
    on_label: str
    off_value: str
    off_label: str


# Defines all entities for switches.
#
# Each entry is defined with a tuple of these values:
#  - module id (str)
#  - process data id (str)
#  - entity name suffix (str)
#  - on Value (str)
#  - on Label (str)
#  - off Value (str)
#  - off Label (str)
SWITCH_SETTINGS_DATA = [
    SwitchData(
        "devices:local",
        "Battery:Strategy",
        "Battery Strategy",
        "1",
        "1",
        "Automatic",
        "2",
        "Automatic economical",
    ),
]


class SelectData(NamedTuple):
    """Representation of a SelectData tuple."""

    module_id: str
    data_id: str
    name: str
    options: list
    is_on: str


# Defines all entities for select widgets.
#
# Each entry is defined with a tuple of these values:
#  - module id (str)
#  - process data id (str)
#  - entity name suffix (str)
#  - options
#  - entity is enabled by default (bool)
SELECT_SETTINGS_DATA = [
    SelectData(
        "devices:local",
        "battery_charge",
        "Battery Charging / Usage mode",
        ["None", "Battery:SmartBatteryControl:Enable", "Battery:TimeControl:Enable"],
        "1",
    )
]
