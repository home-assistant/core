"""Constants for the Kostal Plenticore Solar Inverter integration."""

from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
)

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
            ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER,
            ATTR_ENABLED_DEFAULT: True,
        },
        "format_round",
    ),
    (
        "devices:local",
        "Grid_P",
        "Grid Power",
        {
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER,
            ATTR_ENABLED_DEFAULT: True,
        },
        "format_round",
    ),
    (
        "devices:local",
        "HomeBat_P",
        "Home Power from Battery",
        {ATTR_UNIT_OF_MEASUREMENT: POWER_WATT, ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER},
        "format_round",
    ),
    (
        "devices:local",
        "HomeGrid_P",
        "Home Power from Grid",
        {ATTR_UNIT_OF_MEASUREMENT: POWER_WATT, ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER},
        "format_round",
    ),
    (
        "devices:local",
        "HomeOwn_P",
        "Home Power from Own",
        {ATTR_UNIT_OF_MEASUREMENT: POWER_WATT, ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER},
        "format_round",
    ),
    (
        "devices:local",
        "HomePv_P",
        "Home Power from PV",
        {ATTR_UNIT_OF_MEASUREMENT: POWER_WATT, ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER},
        "format_round",
    ),
    (
        "devices:local",
        "Home_P",
        "Home Power",
        {ATTR_UNIT_OF_MEASUREMENT: POWER_WATT, ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER},
        "format_round",
    ),
    (
        "devices:local:ac",
        "P",
        "AC Power",
        {
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER,
            ATTR_ENABLED_DEFAULT: True,
        },
        "format_round",
    ),
    (
        "devices:local:pv1",
        "P",
        "DC1 Power",
        {ATTR_UNIT_OF_MEASUREMENT: POWER_WATT, ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER},
        "format_round",
    ),
    (
        "devices:local:pv2",
        "P",
        "DC2 Power",
        {ATTR_UNIT_OF_MEASUREMENT: POWER_WATT, ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER},
        "format_round",
    ),
    (
        "devices:local",
        "PV2Bat_P",
        "PV to Battery Power",
        {ATTR_UNIT_OF_MEASUREMENT: POWER_WATT, ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER},
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
        {ATTR_ICON: "mdi:recycle"},
        "format_round",
    ),
    (
        "devices:local:battery",
        "P",
        "Battery Power",
        {ATTR_UNIT_OF_MEASUREMENT: POWER_WATT, ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER},
        "format_round",
    ),
    (
        "devices:local:battery",
        "SoC",
        "Battery SoC",
        {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE, ATTR_DEVICE_CLASS: DEVICE_CLASS_BATTERY},
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
        {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE, ATTR_ICON: "mdi:chart-donut"},
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
        {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE, ATTR_ICON: "mdi:chart-donut"},
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
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHome:Month",
        "Home Consumption Month",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHome:Year",
        "Home Consumption Year",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHome:Total",
        "Home Consumption Total",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHomeBat:Day",
        "Home Consumption from Battery Day",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHomeBat:Month",
        "Home Consumption from Battery Month",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHomeBat:Year",
        "Home Consumption from Battery Year",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHomeBat:Total",
        "Home Consumption from Battery Total",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHomeGrid:Day",
        "Home Consumption from Grid Day",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHomeGrid:Month",
        "Home Consumption from Grid Month",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHomeGrid:Year",
        "Home Consumption from Grid Year",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHomeGrid:Total",
        "Home Consumption from Grid Total",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHomePv:Day",
        "Home Consumption from PV Day",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHomePv:Month",
        "Home Consumption from PV Month",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHomePv:Year",
        "Home Consumption from PV Year",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyHomePv:Total",
        "Home Consumption from PV Total",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyPv1:Day",
        "Energy PV1 Day",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyPv1:Month",
        "Energy PV1 Month",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyPv1:Year",
        "Energy PV1 Year",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyPv1:Total",
        "Energy PV1 Total",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyPv2:Day",
        "Energy PV2 Day",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyPv2:Month",
        "Energy PV2 Month",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyPv2:Year",
        "Energy PV2 Year",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:EnergyPv2:Total",
        "Energy PV2 Total",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:Yield:Day",
        "Energy Yield Day",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
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
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:Yield:Year",
        "Energy Yield Year",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        },
        "format_energy",
    ),
    (
        "scb:statistic:EnergyFlow",
        "Statistic:Yield:Total",
        "Energy Yield Total",
        {
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        },
        "format_energy",
    ),
]

# Defines all entities for settings.
#
# Each entry is defined with a tuple of these values:
#  - module id (str)
#  - process data id (str)
#  - entity name suffix (str)
#  - sensor properties (dict)
#  - value formatter (str)
SENSOR_SETTINGS_DATA = [
    (
        "devices:local",
        "Battery:MinHomeComsumption",
        "Battery min Home Consumption",
        {ATTR_UNIT_OF_MEASUREMENT: POWER_WATT, ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER},
        "format_round",
    ),
    (
        "devices:local",
        "Battery:MinSoc",
        "Battery min Soc",
        {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE, ATTR_ICON: "mdi:battery-negative"},
        "format_round",
    ),
    (
        "devices:local",
        "Battery:Strategy",
        "Battery Strategy",
        {},
        "format_round",
    ),
]
