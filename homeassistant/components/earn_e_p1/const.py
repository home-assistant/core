"""Constants for the EARN-E P1 Meter integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfVolume,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
)

DOMAIN = "earn_e_p1"
DEFAULT_PORT = 16121


@dataclass(frozen=True, kw_only=True)
class P1SensorFieldDescriptor:
    """Describes a sensor field from the P1 meter JSON payload."""

    key: str
    json_key: str
    translation_key: str
    native_unit_of_measurement: str | None
    device_class: SensorDeviceClass | None
    state_class: SensorStateClass | None
    realtime: bool


SENSOR_FIELDS: tuple[P1SensorFieldDescriptor, ...] = (
    P1SensorFieldDescriptor(
        key="power_delivered",
        json_key="power_delivered",
        translation_key="power_delivered",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        realtime=True,
    ),
    P1SensorFieldDescriptor(
        key="power_returned",
        json_key="power_returned",
        translation_key="power_returned",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        realtime=True,
    ),
    P1SensorFieldDescriptor(
        key="voltage_l1",
        json_key="voltage_l1",
        translation_key="voltage_l1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        realtime=True,
    ),
    P1SensorFieldDescriptor(
        key="current_l1",
        json_key="current_l1",
        translation_key="current_l1",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        realtime=True,
    ),
    P1SensorFieldDescriptor(
        key="energy_delivered_tariff1",
        json_key="energy_delivered_tariff1",
        translation_key="energy_delivered_tariff1",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        realtime=False,
    ),
    P1SensorFieldDescriptor(
        key="energy_delivered_tariff2",
        json_key="energy_delivered_tariff2",
        translation_key="energy_delivered_tariff2",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        realtime=False,
    ),
    P1SensorFieldDescriptor(
        key="energy_returned_tariff1",
        json_key="energy_returned_tariff1",
        translation_key="energy_returned_tariff1",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        realtime=False,
    ),
    P1SensorFieldDescriptor(
        key="energy_returned_tariff2",
        json_key="energy_returned_tariff2",
        translation_key="energy_returned_tariff2",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        realtime=False,
    ),
    P1SensorFieldDescriptor(
        key="gas_delivered",
        json_key="gas_delivered",
        translation_key="gas_delivered",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        realtime=False,
    ),
    P1SensorFieldDescriptor(
        key="wifi_rssi",
        json_key="wifiRSSI",
        translation_key="wifi_rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        realtime=False,
    ),
)
