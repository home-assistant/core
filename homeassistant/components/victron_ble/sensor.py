"""Sensor platform for Victron BLE."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from sensor_state_data import DeviceKey
from victron_ble_ha_parser import Keys, Units

from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.sensor import sensor_device_info_to_hass_device_info

LOGGER = logging.getLogger(__name__)

AC_IN_OPTIONS = [
    "ac_in_1",
    "ac_in_2",
    "not_connected",
]

ALARM_OPTIONS = [
    "low_voltage",
    "high_voltage",
    "low_soc",
    "low_starter_voltage",
    "high_starter_voltage",
    "low_temperature",
    "high_temperature",
    "mid_voltage",
    "overload",
    "dc_ripple",
    "low_v_ac_out",
    "high_v_ac_out",
    "short_circuit",
    "bms_lockout",
]

CHARGER_ERROR_OPTIONS = [
    "no_error",
    "temperature_battery_high",
    "voltage_high",
    "remote_temperature_auto_reset",
    "remote_temperature_not_auto_reset",
    "remote_battery",
    "high_ripple",
    "temperature_battery_low",
    "temperature_charger",
    "over_current",
    "bulk_time",
    "current_sensor",
    "internal_temperature",
    "fan",
    "overheated",
    "short_circuit",
    "converter_issue",
    "over_charge",
    "input_voltage",
    "input_current",
    "input_power",
    "input_shutdown_voltage",
    "input_shutdown_current",
    "input_shutdown_failure",
    "inverter_shutdown_pv_isolation",
    "inverter_shutdown_ground_fault",
    "inverter_overload",
    "inverter_temperature",
    "inverter_peak_current",
    "inverter_output_voltage",
    "inverter_self_test",
    "inverter_ac",
    "communication",
    "synchronisation",
    "bms",
    "network",
    "pv_input_shutdown",
    "cpu_temperature",
    "calibration_lost",
    "firmware",
    "settings",
    "tester_fail",
    "internal_dc_voltage",
    "self_test",
    "internal_supply",
]


def error_to_state(value: float | str | None) -> str | None:
    """Convert error code to state string."""
    value_map: dict[Any, str] = {
        "internal_supply_a": "internal_supply",
        "internal_supply_b": "internal_supply",
        "internal_supply_c": "internal_supply",
        "internal_supply_d": "internal_supply",
        "inverter_shutdown_41": "inverter_shutdown_pv_isolation",
        "inverter_shutdown_42": "inverter_shutdown_pv_isolation",
        "inverter_shutdown_43": "inverter_shutdown_ground_fault",
        "internal_temperature_a": "internal_temperature",
        "internal_temperature_b": "internal_temperature",
        "inverter_output_voltage_a": "inverter_output_voltage",
        "inverter_output_voltage_b": "inverter_output_voltage",
        "internal_dc_voltage_a": "internal_dc_voltage",
        "internal_dc_voltage_b": "internal_dc_voltage",
        "remote_temperature_a": "remote_temperature_auto_reset",
        "remote_temperature_b": "remote_temperature_auto_reset",
        "remote_temperature_c": "remote_temperature_not_auto_reset",
        "remote_battery_a": "remote_battery",
        "remote_battery_b": "remote_battery",
        "remote_battery_c": "remote_battery",
        "pv_input_shutdown_80": "pv_input_shutdown",
        "pv_input_shutdown_81": "pv_input_shutdown",
        "pv_input_shutdown_82": "pv_input_shutdown",
        "pv_input_shutdown_83": "pv_input_shutdown",
        "pv_input_shutdown_84": "pv_input_shutdown",
        "pv_input_shutdown_85": "pv_input_shutdown",
        "pv_input_shutdown_86": "pv_input_shutdown",
        "pv_input_shutdown_87": "pv_input_shutdown",
        "inverter_self_test_a": "inverter_self_test",
        "inverter_self_test_b": "inverter_self_test",
        "inverter_self_test_c": "inverter_self_test",
        "network_a": "network",
        "network_b": "network",
        "network_c": "network",
        "network_d": "network",
    }
    return value_map.get(value)


DEVICE_STATE_OPTIONS = [
    "off",
    "low_power",
    "fault",
    "bulk",
    "absorption",
    "float",
    "storage",
    "equalize_manual",
    "inverting",
    "power_supply",
    "starting_up",
    "repeated_absorption",
    "recondition",
    "battery_safe",
    "active",
    "external_control",
    "not_available",
]

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class VictronBLESensorEntityDescription(SensorEntityDescription):
    """Describes Victron BLE sensor entity."""

    value_fn: Callable[[float | int | str | None], float | int | str | None] = (
        lambda x: x
    )


SENSOR_DESCRIPTIONS = {
    Keys.AC_IN_POWER: VictronBLESensorEntityDescription(
        key=Keys.AC_IN_POWER,
        translation_key=Keys.AC_IN_POWER,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.AC_IN_STATE: VictronBLESensorEntityDescription(
        key=Keys.AC_IN_STATE,
        device_class=SensorDeviceClass.ENUM,
        translation_key="ac_in_state",
        options=AC_IN_OPTIONS,
    ),
    Keys.AC_OUT_POWER: VictronBLESensorEntityDescription(
        key=Keys.AC_OUT_POWER,
        translation_key=Keys.AC_OUT_POWER,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.AC_OUT_STATE: VictronBLESensorEntityDescription(
        key=Keys.AC_OUT_STATE,
        device_class=SensorDeviceClass.ENUM,
        translation_key="device_state",
        options=DEVICE_STATE_OPTIONS,
    ),
    Keys.ALARM: VictronBLESensorEntityDescription(
        key=Keys.ALARM,
        device_class=SensorDeviceClass.ENUM,
        translation_key="alarm",
        options=ALARM_OPTIONS,
    ),
    Keys.BALANCER_STATUS: VictronBLESensorEntityDescription(
        key=Keys.BALANCER_STATUS,
        device_class=SensorDeviceClass.ENUM,
        translation_key="balancer_status",
        options=["balanced", "balancing", "imbalance"],
    ),
    Keys.BATTERY_CURRENT: VictronBLESensorEntityDescription(
        key=Keys.BATTERY_CURRENT,
        translation_key=Keys.BATTERY_CURRENT,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.BATTERY_TEMPERATURE: VictronBLESensorEntityDescription(
        key=Keys.BATTERY_TEMPERATURE,
        translation_key=Keys.BATTERY_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.BATTERY_VOLTAGE: VictronBLESensorEntityDescription(
        key=Keys.BATTERY_VOLTAGE,
        translation_key=Keys.BATTERY_VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.CHARGER_ERROR: VictronBLESensorEntityDescription(
        key=Keys.CHARGER_ERROR,
        device_class=SensorDeviceClass.ENUM,
        translation_key="charger_error",
        options=CHARGER_ERROR_OPTIONS,
        value_fn=error_to_state,
    ),
    Keys.CONSUMED_AMPERE_HOURS: VictronBLESensorEntityDescription(
        key=Keys.CONSUMED_AMPERE_HOURS,
        translation_key=Keys.CONSUMED_AMPERE_HOURS,
        native_unit_of_measurement=Units.ELECTRIC_CURRENT_FLOW_AMPERE_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.CURRENT: VictronBLESensorEntityDescription(
        key=Keys.CURRENT,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.DEVICE_STATE: VictronBLESensorEntityDescription(
        key=Keys.DEVICE_STATE,
        device_class=SensorDeviceClass.ENUM,
        translation_key="device_state",
        options=DEVICE_STATE_OPTIONS,
    ),
    Keys.ERROR_CODE: VictronBLESensorEntityDescription(
        key=Keys.ERROR_CODE,
        device_class=SensorDeviceClass.ENUM,
        translation_key="charger_error",
        options=CHARGER_ERROR_OPTIONS,
    ),
    Keys.EXTERNAL_DEVICE_LOAD: VictronBLESensorEntityDescription(
        key=Keys.EXTERNAL_DEVICE_LOAD,
        translation_key=Keys.EXTERNAL_DEVICE_LOAD,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.INPUT_VOLTAGE: VictronBLESensorEntityDescription(
        key=Keys.INPUT_VOLTAGE,
        translation_key=Keys.INPUT_VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.METER_TYPE: VictronBLESensorEntityDescription(
        key=Keys.METER_TYPE,
        device_class=SensorDeviceClass.ENUM,
        translation_key="meter_type",
        options=[
            "solar_charger",
            "wind_charger",
            "shaft_generator",
            "alternator",
            "fuel_cell",
            "water_generator",
            "dc_dc_charger",
            "ac_charger",
            "generic_source",
            "generic_load",
            "electric_drive",
            "fridge",
            "water_pump",
            "bilge_pump",
            "dc_system",
            "inverter",
            "water_heater",
        ],
    ),
    Keys.MIDPOINT_VOLTAGE: VictronBLESensorEntityDescription(
        key=Keys.MIDPOINT_VOLTAGE,
        translation_key=Keys.MIDPOINT_VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.OFF_REASON: VictronBLESensorEntityDescription(
        key=Keys.OFF_REASON,
        device_class=SensorDeviceClass.ENUM,
        translation_key="off_reason",
        options=[
            "no_reason",
            "no_input_power",
            "switched_off_switch",
            "switched_off_register",
            "remote_input",
            "protection_active",
            "pay_as_you_go_out_of_credit",
            "bms",
            "engine_shutdown",
            "analysing_input_voltage",
        ],
    ),
    Keys.OUTPUT_VOLTAGE: VictronBLESensorEntityDescription(
        key=Keys.OUTPUT_VOLTAGE,
        translation_key=Keys.OUTPUT_VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.REMAINING_MINUTES: VictronBLESensorEntityDescription(
        key=Keys.REMAINING_MINUTES,
        translation_key=Keys.REMAINING_MINUTES,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorDeviceClass.SIGNAL_STRENGTH: VictronBLESensorEntityDescription(
        key=SensorDeviceClass.SIGNAL_STRENGTH.value,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.SOLAR_POWER: VictronBLESensorEntityDescription(
        key=Keys.SOLAR_POWER,
        translation_key=Keys.SOLAR_POWER,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.STARTER_VOLTAGE: VictronBLESensorEntityDescription(
        key=Keys.STARTER_VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.STATE_OF_CHARGE: VictronBLESensorEntityDescription(
        key=Keys.STATE_OF_CHARGE,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.TEMPERATURE: VictronBLESensorEntityDescription(
        key=Keys.TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.VOLTAGE: VictronBLESensorEntityDescription(
        key=Keys.VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.WARNING: VictronBLESensorEntityDescription(
        key=Keys.WARNING,
        device_class=SensorDeviceClass.ENUM,
        translation_key="alarm",
        options=ALARM_OPTIONS,
    ),
    Keys.YIELD_TODAY: VictronBLESensorEntityDescription(
        key=Keys.YIELD_TODAY,
        translation_key=Keys.YIELD_TODAY,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
}

for i in range(1, 8):
    cell_key = getattr(Keys, f"CELL_{i}_VOLTAGE")
    SENSOR_DESCRIPTIONS[cell_key] = VictronBLESensorEntityDescription(
        key=cell_key,
        translation_key="cell_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    )


def _device_key_to_bluetooth_entity_key(
    device_key: DeviceKey,
) -> PassiveBluetoothEntityKey:
    """Convert a device key to an entity key."""
    return PassiveBluetoothEntityKey(device_key.key, device_key.device_id)


def sensor_update_to_bluetooth_data_update(
    sensor_update,
) -> PassiveBluetoothDataUpdate:
    """Convert a sensor update to a bluetooth data update."""
    return PassiveBluetoothDataUpdate(
        devices={
            device_id: sensor_device_info_to_hass_device_info(device_info)
            for device_id, device_info in sensor_update.devices.items()
        },
        entity_descriptions={
            _device_key_to_bluetooth_entity_key(device_key): SENSOR_DESCRIPTIONS[
                device_key.key
            ]
            for device_key in sensor_update.entity_descriptions
            if device_key.key in SENSOR_DESCRIPTIONS
        },
        entity_data={
            _device_key_to_bluetooth_entity_key(device_key): sensor_values.native_value
            for device_key, sensor_values in sensor_update.entity_values.items()
            if device_key.key in SENSOR_DESCRIPTIONS
        },
        entity_names={},
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Victron BLE sensor."""
    coordinator = entry.runtime_data
    processor = PassiveBluetoothDataProcessor(sensor_update_to_bluetooth_data_update)
    entry.async_on_unload(
        processor.async_add_entities_listener(
            VictronBLESensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(coordinator.async_register_processor(processor))


class VictronBLESensorEntity(PassiveBluetoothProcessorEntity, SensorEntity):
    """Representation of Victron BLE sensor."""

    entity_description: VictronBLESensorEntityDescription

    @property
    def native_value(self) -> float | int | str | None:
        """Return the state of the sensor."""
        value = self.processor.entity_data.get(self.entity_key)

        return self.entity_description.value_fn(value)
