"""Platform for Kostal Plenticore sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
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


@dataclass
class PlenticoreRequiredKeysMixin:
    """A class that describes required properties for plenticore sensor entities."""

    module_id: str
    properties: dict[str, Any]
    formatter: str


@dataclass
class PlenticoreSensorEntityDescription(
    SensorEntityDescription, PlenticoreRequiredKeysMixin
):
    """A class that describes plenticore sensor entities."""


SENSOR_PROCESS_DATA = [
    PlenticoreSensorEntityDescription(
        module_id="devices:local",
        key="Inverter:State",
        name="Inverter State",
        properties={ATTR_ICON: "mdi:state-machine"},
        formatter="format_inverter_state",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local",
        key="Dc_P",
        name="Solar Power",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_ENABLED_DEFAULT: True,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local",
        key="Grid_P",
        name="Grid Power",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_ENABLED_DEFAULT: True,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local",
        key="HomeBat_P",
        name="Home Power from Battery",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
        },
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local",
        key="HomeGrid_P",
        name="Home Power from Grid",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local",
        key="HomeOwn_P",
        name="Home Power from Own",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local",
        key="HomePv_P",
        name="Home Power from PV",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local",
        key="Home_P",
        name="Home Power",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local:ac",
        key="P",
        name="AC Power",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_ENABLED_DEFAULT: True,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local:pv1",
        key="P",
        name="DC1 Power",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local:pv1",
        key="U",
        name="DC1 Voltage",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local:pv1",
        key="I",
        name="DC1 Current",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
            ATTR_DEVICE_CLASS: SensorDeviceClass.CURRENT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        formatter="format_float",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local:pv2",
        key="P",
        name="DC2 Power",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local:pv2",
        key="U",
        name="DC2 Voltage",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local:pv2",
        key="I",
        name="DC2 Current",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
            ATTR_DEVICE_CLASS: SensorDeviceClass.CURRENT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        formatter="format_float",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local:pv3",
        key="P",
        name="DC3 Power",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local:pv3",
        key="U",
        name="DC3 Voltage",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local:pv3",
        key="I",
        name="DC3 Current",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
            ATTR_DEVICE_CLASS: SensorDeviceClass.CURRENT,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        formatter="format_float",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local",
        key="PV2Bat_P",
        name="PV to Battery Power",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local",
        key="EM_State",
        name="Energy Manager State",
        properties={ATTR_ICON: "mdi:state-machine"},
        formatter="format_em_manager_state",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local:battery",
        key="Cycles",
        name="Battery Cycles",
        properties={
            ATTR_ICON: "mdi:recycle",
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local:battery",
        key="P",
        name="Battery Power",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.POWER,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local:battery",
        key="SoC",
        name="Battery SoC",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            ATTR_DEVICE_CLASS: SensorDeviceClass.BATTERY,
        },
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:Autarky:Day",
        name="Autarky Day",
        properties={ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE, ATTR_ICON: "mdi:chart-donut"},
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:Autarky:Month",
        name="Autarky Month",
        properties={ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE, ATTR_ICON: "mdi:chart-donut"},
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:Autarky:Total",
        name="Autarky Total",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            ATTR_ICON: "mdi:chart-donut",
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:Autarky:Year",
        name="Autarky Year",
        properties={ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE, ATTR_ICON: "mdi:chart-donut"},
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:OwnConsumptionRate:Day",
        name="Own Consumption Rate Day",
        properties={ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE, ATTR_ICON: "mdi:chart-donut"},
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:OwnConsumptionRate:Month",
        name="Own Consumption Rate Month",
        properties={ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE, ATTR_ICON: "mdi:chart-donut"},
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:OwnConsumptionRate:Total",
        name="Own Consumption Rate Total",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            ATTR_ICON: "mdi:chart-donut",
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:OwnConsumptionRate:Year",
        name="Own Consumption Rate Year",
        properties={ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE, ATTR_ICON: "mdi:chart-donut"},
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyHome:Day",
        name="Home Consumption Day",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyHome:Month",
        name="Home Consumption Month",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyHome:Year",
        name="Home Consumption Year",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyHome:Total",
        name="Home Consumption Total",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyHomeBat:Day",
        name="Home Consumption from Battery Day",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyHomeBat:Month",
        name="Home Consumption from Battery Month",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyHomeBat:Year",
        name="Home Consumption from Battery Year",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyHomeBat:Total",
        name="Home Consumption from Battery Total",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyHomeGrid:Day",
        name="Home Consumption from Grid Day",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyHomeGrid:Month",
        name="Home Consumption from Grid Month",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyHomeGrid:Year",
        name="Home Consumption from Grid Year",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyHomeGrid:Total",
        name="Home Consumption from Grid Total",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyHomePv:Day",
        name="Home Consumption from PV Day",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyHomePv:Month",
        name="Home Consumption from PV Month",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyHomePv:Year",
        name="Home Consumption from PV Year",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyHomePv:Total",
        name="Home Consumption from PV Total",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyPv1:Day",
        name="Energy PV1 Day",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyPv1:Month",
        name="Energy PV1 Month",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyPv1:Year",
        name="Energy PV1 Year",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyPv1:Total",
        name="Energy PV1 Total",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyPv2:Day",
        name="Energy PV2 Day",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyPv2:Month",
        name="Energy PV2 Month",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyPv2:Year",
        name="Energy PV2 Year",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyPv2:Total",
        name="Energy PV2 Total",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyPv3:Day",
        name="Energy PV3 Day",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyPv3:Month",
        name="Energy PV3 Month",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyPv3:Year",
        name="Energy PV3 Year",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyPv3:Total",
        name="Energy PV3 Total",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:Yield:Day",
        name="Energy Yield Day",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_ENABLED_DEFAULT: True,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:Yield:Month",
        name="Energy Yield Month",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:Yield:Year",
        name="Energy Yield Year",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:Yield:Total",
        name="Energy Yield Total",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyChargeGrid:Day",
        name="Battery Charge from Grid Day",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyChargeGrid:Month",
        name="Battery Charge from Grid Month",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyChargeGrid:Year",
        name="Battery Charge from Grid Year",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyChargeGrid:Total",
        name="Battery Charge from Grid Total",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyChargePv:Day",
        name="Battery Charge from PV Day",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyChargePv:Month",
        name="Battery Charge from PV Month",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyChargePv:Year",
        name="Battery Charge from PV Year",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyChargePv:Total",
        name="Battery Charge from PV Total",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyDischargeGrid:Day",
        name="Energy Discharge to Grid Day",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyDischargeGrid:Month",
        name="Energy Discharge to Grid Month",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyDischargeGrid:Year",
        name="Energy Discharge to Grid Year",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        },
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="scb:statistic:EnergyFlow",
        key="Statistic:EnergyDischargeGrid:Total",
        name="Energy Discharge to Grid Total",
        properties={
            ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
        formatter="format_energy",
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
    for description in SENSOR_PROCESS_DATA:
        module_id = description.module_id
        data_id = description.key
        name = description.name
        sensor_data = description.properties
        fmt = description.formatter
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
        sensor_name: str | None,
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
