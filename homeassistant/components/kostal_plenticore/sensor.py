"""Platform for Kostal Plenticore sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODULE_IDS
from .coordinator import ProcessDataUpdateCoordinator
from .helper import PlenticoreDataFormatter

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PlenticoreSensorEntityDescription(SensorEntityDescription):
    """A class that describes plenticore sensor entities."""

    module_id: str
    formatter: str


SENSOR_PROCESS_DATA = [
    PlenticoreSensorEntityDescription(
        module_id="devices:local",
        key="Inverter:State",
        name="Inverter State",
        icon="mdi:state-machine",
        formatter="format_inverter_state",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local",
        key="Dc_P",
        name="Solar Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=True,
        state_class=SensorStateClass.MEASUREMENT,
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local",
        key="Grid_P",
        name="Grid Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=True,
        state_class=SensorStateClass.MEASUREMENT,
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local",
        key="HomeBat_P",
        name="Home Power from Battery",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local",
        key="HomeGrid_P",
        name="Home Power from Grid",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local",
        key="HomeOwn_P",
        name="Home Power from Own",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local",
        key="HomePv_P",
        name="Home Power from PV",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local",
        key="Home_P",
        name="Home Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local:ac",
        key="P",
        name="AC Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=True,
        state_class=SensorStateClass.MEASUREMENT,
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local:pv1",
        key="P",
        name="DC1 Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local:pv1",
        key="U",
        name="DC1 Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local:pv1",
        key="I",
        name="DC1 Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter="format_float",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local:pv2",
        key="P",
        name="DC2 Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local:pv2",
        key="U",
        name="DC2 Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local:pv2",
        key="I",
        name="DC2 Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter="format_float",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local:pv3",
        key="P",
        name="DC3 Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local:pv3",
        key="U",
        name="DC3 Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local:pv3",
        key="I",
        name="DC3 Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        formatter="format_float",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local",
        key="PV2Bat_P",
        name="PV to Battery Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local",
        key="EM_State",
        name="Energy Manager State",
        icon="mdi:state-machine",
        formatter="format_em_manager_state",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local:battery",
        key="Cycles",
        name="Battery Cycles",
        icon="mdi:recycle",
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local:battery",
        key="P",
        name="Battery Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="devices:local:battery",
        key="SoC",
        name="Battery SoC",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:Autarky:Day",
        name="Autarky Day",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:chart-donut",
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:Autarky:Month",
        name="Autarky Month",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:chart-donut",
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:Autarky:Total",
        name="Autarky Total",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:chart-donut",
        state_class=SensorStateClass.MEASUREMENT,
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:Autarky:Year",
        name="Autarky Year",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:chart-donut",
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:OwnConsumptionRate:Day",
        name="Own Consumption Rate Day",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:chart-donut",
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:OwnConsumptionRate:Month",
        name="Own Consumption Rate Month",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:chart-donut",
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:OwnConsumptionRate:Total",
        name="Own Consumption Rate Total",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:chart-donut",
        state_class=SensorStateClass.MEASUREMENT,
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:OwnConsumptionRate:Year",
        name="Own Consumption Rate Year",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:chart-donut",
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyHome:Day",
        name="Home Consumption Day",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyHome:Month",
        name="Home Consumption Month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyHome:Year",
        name="Home Consumption Year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyHome:Total",
        name="Home Consumption Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyHomeBat:Day",
        name="Home Consumption from Battery Day",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyHomeBat:Month",
        name="Home Consumption from Battery Month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyHomeBat:Year",
        name="Home Consumption from Battery Year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyHomeBat:Total",
        name="Home Consumption from Battery Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyHomeGrid:Day",
        name="Home Consumption from Grid Day",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyHomeGrid:Month",
        name="Home Consumption from Grid Month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyHomeGrid:Year",
        name="Home Consumption from Grid Year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyHomeGrid:Total",
        name="Home Consumption from Grid Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyHomePv:Day",
        name="Home Consumption from PV Day",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyHomePv:Month",
        name="Home Consumption from PV Month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyHomePv:Year",
        name="Home Consumption from PV Year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyHomePv:Total",
        name="Home Consumption from PV Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyPv1:Day",
        name="Energy PV1 Day",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyPv1:Month",
        name="Energy PV1 Month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyPv1:Year",
        name="Energy PV1 Year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyPv1:Total",
        name="Energy PV1 Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyPv2:Day",
        name="Energy PV2 Day",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyPv2:Month",
        name="Energy PV2 Month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyPv2:Year",
        name="Energy PV2 Year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyPv2:Total",
        name="Energy PV2 Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyPv3:Day",
        name="Energy PV3 Day",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyPv3:Month",
        name="Energy PV3 Month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyPv3:Year",
        name="Energy PV3 Year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyPv3:Total",
        name="Energy PV3 Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:Yield:Day",
        name="Energy Yield Day",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        entity_registry_enabled_default=True,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:Yield:Month",
        name="Energy Yield Month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:Yield:Year",
        name="Energy Yield Year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:Yield:Total",
        name="Energy Yield Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyChargeGrid:Day",
        name="Battery Charge from Grid Day",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyChargeGrid:Month",
        name="Battery Charge from Grid Month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyChargeGrid:Year",
        name="Battery Charge from Grid Year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyChargeGrid:Total",
        name="Battery Charge from Grid Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyChargePv:Day",
        name="Battery Charge from PV Day",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyChargePv:Month",
        name="Battery Charge from PV Month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyChargePv:Year",
        name="Battery Charge from PV Year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyChargePv:Total",
        name="Battery Charge from PV Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyDischarge:Day",
        name="Battery Discharge Day",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyDischarge:Month",
        name="Battery Discharge Month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyDischarge:Year",
        name="Battery Discharge Year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyDischarge:Total",
        name="Battery Discharge Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyDischargeGrid:Day",
        name="Energy Discharge to Grid Day",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyDischargeGrid:Month",
        name="Energy Discharge to Grid Month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyDischargeGrid:Year",
        name="Energy Discharge to Grid Year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id=MODULE_IDS["energy_flow"],
        key="Statistic:EnergyDischargeGrid:Total",
        name="Energy Discharge to Grid Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="_virt_",
        key="pv_P",
        name="Sum power of all PV DC inputs",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=True,
        state_class=SensorStateClass.MEASUREMENT,
        formatter="format_round",
    ),
    PlenticoreSensorEntityDescription(
        module_id="_virt_",
        key="Statistic:EnergyGrid:Total",
        name="Energy to Grid Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="_virt_",
        key="Statistic:EnergyGrid:Year",
        name="Energy to Grid Year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="_virt_",
        key="Statistic:EnergyGrid:Month",
        name="Energy to Grid Month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        formatter="format_energy",
    ),
    PlenticoreSensorEntityDescription(
        module_id="_virt_",
        key="Statistic:EnergyGrid:Day",
        name="Energy to Grid Day",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
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
                description,
                entry.entry_id,
                entry.title,
                plenticore.device_info,
            )
        )

    async_add_entities(entities)


class PlenticoreDataSensor(
    CoordinatorEntity[ProcessDataUpdateCoordinator], SensorEntity
):
    """Representation of a Plenticore data Sensor."""

    entity_description: PlenticoreSensorEntityDescription

    def __init__(
        self,
        coordinator: ProcessDataUpdateCoordinator,
        description: PlenticoreSensorEntityDescription,
        entry_id: str,
        platform_name: str,
        device_info: DeviceInfo,
    ) -> None:
        """Create a new Sensor Entity for Plenticore process data."""
        super().__init__(coordinator)
        self.entity_description = description
        self.entry_id = entry_id
        self.module_id = description.module_id
        self.data_id = description.key

        self._formatter: Callable[[str], Any] = PlenticoreDataFormatter.get_method(
            description.formatter
        )

        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry_id}_{self.module_id}_{self.data_id}"
        self._attr_name = f"{platform_name} {description.name}"

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
        self.async_on_remove(
            self.coordinator.start_fetch_data(self.module_id, self.data_id)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister this entity from the Update Coordinator."""
        self.coordinator.stop_fetch_data(self.module_id, self.data_id)
        await super().async_will_remove_from_hass()

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            # None is translated to STATE_UNKNOWN
            return None

        raw_value = self.coordinator.data[self.module_id][self.data_id]

        return self._formatter(raw_value)
