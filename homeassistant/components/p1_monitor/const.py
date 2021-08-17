"""Constants for the P1 Monitor integration."""
from __future__ import annotations

import logging
from typing import Final

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntityDescription,
)
from homeassistant.const import (
    CURRENCY_EURO,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
    VOLUME_CUBIC_METERS,
)
from homeassistant.util import dt

DOMAIN: Final = "p1_monitor"
LOGGER = logging.getLogger(__package__)
DEFAULT_TIME_BETWEEN_UPDATE = 5

ATTR_ENTRY_TYPE: Final = "entry_type"
ENTRY_TYPE_SERVICE: Final = "service"

CONF_TIME_BETWEEN_UPDATE = "time_between_update"

SERVICE_SMARTMETER: Final = "smartmeter"
SERVICE_PHASES: Final = "phases"
SERVICE_SETTINGS: Final = "settings"

SERVICES: dict[str, str] = {
    SERVICE_SMARTMETER: "SmartMeter",
    SERVICE_PHASES: "Phases",
    SERVICE_SETTINGS: "Settings",
}

SENSORS: dict[str, list[SensorEntityDescription]] = {
    SERVICE_SMARTMETER: [
        SensorEntityDescription(
            key="gas_consumption",
            name="Gas Consumption",
            icon="mdi:fire",
            entity_registry_enabled_default=False,
            native_unit_of_measurement=VOLUME_CUBIC_METERS,
            device_class=DEVICE_CLASS_GAS,
            state_class=STATE_CLASS_TOTAL_INCREASING,
            last_reset=dt.utc_from_timestamp(0),
        ),
        SensorEntityDescription(
            key="power_consumption",
            name="Power Consumption",
            native_unit_of_measurement=POWER_WATT,
            device_class=DEVICE_CLASS_POWER,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="energy_consumption_high",
            name="Energy Consumption - High Tariff",
            native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
            device_class=DEVICE_CLASS_ENERGY,
            state_class=STATE_CLASS_TOTAL_INCREASING,
            last_reset=dt.utc_from_timestamp(0),
        ),
        SensorEntityDescription(
            key="energy_consumption_low",
            name="Energy Consumption - Low Tariff",
            native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
            device_class=DEVICE_CLASS_ENERGY,
            state_class=STATE_CLASS_TOTAL_INCREASING,
            last_reset=dt.utc_from_timestamp(0),
        ),
        SensorEntityDescription(
            key="power_production",
            name="Power Production",
            native_unit_of_measurement=POWER_WATT,
            device_class=DEVICE_CLASS_POWER,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="energy_production_high",
            name="Energy Production - High Tariff",
            native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
            device_class=DEVICE_CLASS_ENERGY,
            state_class=STATE_CLASS_TOTAL_INCREASING,
            last_reset=dt.utc_from_timestamp(0),
        ),
        SensorEntityDescription(
            key="energy_production_low",
            name="Energy Production - Low Tariff",
            native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
            device_class=DEVICE_CLASS_ENERGY,
            state_class=STATE_CLASS_TOTAL_INCREASING,
            last_reset=dt.utc_from_timestamp(0),
        ),
        SensorEntityDescription(
            key="energy_tariff_period",
            name="Energy Tariff Period",
            icon="mdi:calendar-clock",
        ),
    ],
    SERVICE_PHASES: [
        SensorEntityDescription(
            key="voltage_phase_l1",
            name="Voltage Phase L1",
            native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
            device_class=DEVICE_CLASS_VOLTAGE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="voltage_phase_l2",
            name="Voltage Phase L2",
            native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
            device_class=DEVICE_CLASS_VOLTAGE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="voltage_phase_l3",
            name="Voltage Phase L3",
            native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
            device_class=DEVICE_CLASS_VOLTAGE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="current_phase_l1",
            name="Current Phase L1",
            native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
            device_class=DEVICE_CLASS_CURRENT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="current_phase_l2",
            name="Current Phase L2",
            native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
            device_class=DEVICE_CLASS_CURRENT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="current_phase_l3",
            name="Current Phase L3",
            native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
            device_class=DEVICE_CLASS_CURRENT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="power_consumed_phase_l1",
            name="Power Consumed Phase L1",
            native_unit_of_measurement=POWER_WATT,
            device_class=DEVICE_CLASS_POWER,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="power_consumed_phase_l2",
            name="Power Consumed Phase L2",
            native_unit_of_measurement=POWER_WATT,
            device_class=DEVICE_CLASS_POWER,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="power_consumed_phase_l3",
            name="Power Consumed Phase L3",
            native_unit_of_measurement=POWER_WATT,
            device_class=DEVICE_CLASS_POWER,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="power_produced_phase_l1",
            name="Power Produced Phase L1",
            native_unit_of_measurement=POWER_WATT,
            device_class=DEVICE_CLASS_POWER,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="power_produced_phase_l2",
            name="Power Produced Phase L2",
            native_unit_of_measurement=POWER_WATT,
            device_class=DEVICE_CLASS_POWER,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="power_produced_phase_l3",
            name="Power Produced Phase L3",
            native_unit_of_measurement=POWER_WATT,
            device_class=DEVICE_CLASS_POWER,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
    ],
    SERVICE_SETTINGS: [
        SensorEntityDescription(
            key="gas_consumption_tariff",
            name="Gas Consumption - Tariff",
            icon="mdi:cash",
            entity_registry_enabled_default=False,
            native_unit_of_measurement=CURRENCY_EURO,
        ),
        SensorEntityDescription(
            key="energy_consumption_low_tariff",
            name="Energy Consumption - Low Tariff",
            icon="mdi:cash",
            native_unit_of_measurement=CURRENCY_EURO,
        ),
        SensorEntityDescription(
            key="energy_consumption_high_tariff",
            name="Energy Consumption - High Tariff",
            icon="mdi:cash",
            native_unit_of_measurement=CURRENCY_EURO,
        ),
        SensorEntityDescription(
            key="energy_production_low_tariff",
            name="Energy Production - Low Tariff",
            icon="mdi:cash",
            native_unit_of_measurement=CURRENCY_EURO,
        ),
        SensorEntityDescription(
            key="energy_production_high_tariff",
            name="Energy Production - High Tariff",
            icon="mdi:cash",
            native_unit_of_measurement=CURRENCY_EURO,
        ),
    ],
}
