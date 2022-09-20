"""Platform for Kostal Plenticore sensors."""
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_ENABLED_DEFAULT, DOMAIN
from .helper import PlenticoreDataFormatter, ProcessDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

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


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add kostal plenticore Sensors."""
    plenticore = hass.data[DOMAIN][entry.entry_id]

    entities = []

    available_process_data = await plenticore.client.get_process_data()
    process_data_update_coordinator = ProcessDataUpdateCoordinator(
        hass,
        _LOGGER,
        "Process Data",
        timedelta(seconds=10),
        plenticore,
    )
    module_id: str
    data_id: str
    name: str
    sensor_data: dict[str, Any]
    fmt: str
    for (  # type: ignore[assignment]
        module_id,
        data_id,
        name,
        sensor_data,
        fmt,
    ) in SENSOR_PROCESS_DATA:
        if (
            module_id not in available_process_data
            or data_id not in available_process_data[module_id]
        ):
            _LOGGER.debug(
                "Skipping non existing process data %s/%s", module_id, data_id
            )
            continue

        entities.append(
            PlenticoreDataSensor(
                process_data_update_coordinator,
                entry.entry_id,
                entry.title,
                module_id,
                data_id,
                name,
                sensor_data,
                PlenticoreDataFormatter.get_method(fmt),
                plenticore.device_info,
                None,
            )
        )

    async_add_entities(entities)


class PlenticoreDataSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Plenticore data Sensor."""

    def __init__(
        self,
        coordinator,
        entry_id: str,
        platform_name: str,
        module_id: str,
        data_id: str,
        sensor_name: str,
        sensor_data: dict[str, Any],
        formatter: Callable[[str], Any],
        device_info: DeviceInfo,
        entity_category: EntityCategory | None,
    ):
        """Create a new Sensor Entity for Plenticore process data."""
        super().__init__(coordinator)
        self.entry_id = entry_id
        self.platform_name = platform_name
        self.module_id = module_id
        self.data_id = data_id

        self._sensor_name = sensor_name
        self._sensor_data = sensor_data
        self._formatter = formatter

        self._device_info = device_info

        self._attr_entity_category = entity_category

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.module_id in self.coordinator.data
            and self.data_id in self.coordinator.data[self.module_id]
        )

    async def async_added_to_hass(self) -> None:
        """Register this entity on the Update Coordinator."""
        await super().async_added_to_hass()
        self.coordinator.start_fetch_data(self.module_id, self.data_id)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister this entity from the Update Coordinator."""
        self.coordinator.stop_fetch_data(self.module_id, self.data_id)
        await super().async_will_remove_from_hass()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self._device_info

    @property
    def unique_id(self) -> str:
        """Return the unique id of this Sensor Entity."""
        return f"{self.entry_id}_{self.module_id}_{self.data_id}"

    @property
    def name(self) -> str:
        """Return the name of this Sensor Entity."""
        return f"{self.platform_name} {self._sensor_name}"

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of this Sensor Entity or None."""
        return self._sensor_data.get(ATTR_UNIT_OF_MEASUREMENT)

    @property
    def icon(self) -> str | None:
        """Return the icon name of this Sensor Entity or None."""
        return self._sensor_data.get(ATTR_ICON)

    @property
    def device_class(self) -> str | None:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._sensor_data.get(ATTR_DEVICE_CLASS)

    @property
    def state_class(self) -> str | None:
        """Return the class of the state of this device, from component STATE_CLASSES."""
        return self._sensor_data.get(ATTR_STATE_CLASS)

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._sensor_data.get(ATTR_ENABLED_DEFAULT, False)

    @property
    def native_value(self) -> Any | None:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            # None is translated to STATE_UNKNOWN
            return None

        raw_value = self.coordinator.data[self.module_id][self.data_id]

        return self._formatter(raw_value) if self._formatter else raw_value
