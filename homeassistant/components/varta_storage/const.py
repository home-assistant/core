"""Constants for the VARTA Storage integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, TIME_HOURS, UnitOfEnergy, UnitOfPower

DOMAIN = "varta_storage"
LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)


@dataclass
class VartaSensorEntityDescription(SensorEntityDescription):
    """Class describing Varta Storage entities."""

    source_key: str | None = None


SENSORS: Final[tuple[VartaSensorEntityDescription, ...]] = (
    VartaSensorEntityDescription(
        key="stateOfCharge",
        name="Charge",
        source_key="soc",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    VartaSensorEntityDescription(
        key="gridPower",
        name="Grid Power",
        source_key="grid_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    VartaSensorEntityDescription(
        key="gridPowerTo",
        name="Power To Grid",
        source_key="to_grid_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    VartaSensorEntityDescription(
        key="gridPowerFrom",
        name="Power From Grid",
        source_key="from_grid_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    VartaSensorEntityDescription(
        key="gridPowerToTotal",
        name="Total Power To Grid",
        source_key="home_to_grid",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    ),
    VartaSensorEntityDescription(
        key="gridPowerFromTotal",
        name="Total Power From Grid",
        source_key="grid_to_home",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    ),
    VartaSensorEntityDescription(
        key="state",
        name="State Number",
        source_key="state",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
    ),
    VartaSensorEntityDescription(
        key="stateText",
        name="State",
        source_key="state_text",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
    ),
    VartaSensorEntityDescription(
        key="errorCode",
        name="Error Code",
        source_key="error_code",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
    ),
    VartaSensorEntityDescription(
        key="powerActive",
        name="Active Power",
        source_key="active_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    VartaSensorEntityDescription(
        key="powerApparent",
        name="Apparent Power",
        source_key="apparent_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    VartaSensorEntityDescription(
        key="powerCharge",
        name="Charging Power",
        source_key="charge_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    VartaSensorEntityDescription(
        key="powerDischarge",
        name="Discharging Power",
        source_key="discharge_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    VartaSensorEntityDescription(
        key="powerChargeTotal",
        name="Total Power Charged",
        source_key="total_charged_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    VartaSensorEntityDescription(
        key="powerChargeTotalNegated",
        name="Total Power Consumed Charging",
        source_key="inverter_total_charged",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    ),
    VartaSensorEntityDescription(
        key="powerDischargeTotal",
        name="Total Power Discharged",
        source_key="inverter_total_discharged",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    ),
    VartaSensorEntityDescription(
        key="cycleCounter",
        name="Charging Cycle Counter",
        source_key="charge_cycle_counter",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
    ),
    VartaSensorEntityDescription(
        key="maintnanceFilterDueIn",
        name="Hours Until Filter Maintenance",
        source_key="hours_until_filter_maintenance",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=TIME_HOURS,
    ),
    VartaSensorEntityDescription(
        key="fan",
        name="Fan",
        source_key="fan",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
    ),
    VartaSensorEntityDescription(
        key="main",
        name="Main",
        source_key="main",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
    ),
)
