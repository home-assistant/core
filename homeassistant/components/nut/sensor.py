"""Provides a sensor to track various status aspects of a UPS."""

from __future__ import annotations

from dataclasses import asdict
import logging
from typing import Final, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_SW_VERSION,
    PERCENTAGE,
    STATE_UNKNOWN,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import NutConfigEntry, PyNUTData
from .const import DOMAIN, KEY_STATUS, KEY_STATUS_DISPLAY, STATE_TYPES

NUT_DEV_INFO_TO_DEV_INFO: dict[str, str] = {
    "manufacturer": ATTR_MANUFACTURER,
    "model": ATTR_MODEL,
    "firmware": ATTR_SW_VERSION,
}

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: Final[dict[str, SensorEntityDescription]] = {
    "ups.status.display": SensorEntityDescription(
        key="ups.status.display",
        translation_key="ups_status_display",
    ),
    "ups.status": SensorEntityDescription(
        key="ups.status",
        translation_key="ups_status",
    ),
    "ups.alarm": SensorEntityDescription(
        key="ups.alarm",
        translation_key="ups_alarm",
    ),
    "ups.temperature": SensorEntityDescription(
        key="ups.temperature",
        translation_key="ups_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "ups.load": SensorEntityDescription(
        key="ups.load",
        translation_key="ups_load",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "ups.load.high": SensorEntityDescription(
        key="ups.load.high",
        translation_key="ups_load_high",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "ups.id": SensorEntityDescription(
        key="ups.id",
        translation_key="ups_id",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "ups.delay.start": SensorEntityDescription(
        key="ups.delay.start",
        translation_key="ups_delay_start",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "ups.delay.reboot": SensorEntityDescription(
        key="ups.delay.reboot",
        translation_key="ups_delay_reboot",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "ups.delay.shutdown": SensorEntityDescription(
        key="ups.delay.shutdown",
        translation_key="ups_delay_shutdown",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "ups.timer.start": SensorEntityDescription(
        key="ups.timer.start",
        translation_key="ups_timer_start",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "ups.timer.reboot": SensorEntityDescription(
        key="ups.timer.reboot",
        translation_key="ups_timer_reboot",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "ups.timer.shutdown": SensorEntityDescription(
        key="ups.timer.shutdown",
        translation_key="ups_timer_shutdown",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "ups.test.interval": SensorEntityDescription(
        key="ups.test.interval",
        translation_key="ups_test_interval",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "ups.test.result": SensorEntityDescription(
        key="ups.test.result",
        translation_key="ups_test_result",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "ups.test.date": SensorEntityDescription(
        key="ups.test.date",
        translation_key="ups_test_date",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "ups.display.language": SensorEntityDescription(
        key="ups.display.language",
        translation_key="ups_display_language",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "ups.contacts": SensorEntityDescription(
        key="ups.contacts",
        translation_key="ups_contacts",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "ups.efficiency": SensorEntityDescription(
        key="ups.efficiency",
        translation_key="ups_efficiency",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "ups.power": SensorEntityDescription(
        key="ups.power",
        translation_key="ups_power",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "ups.power.nominal": SensorEntityDescription(
        key="ups.power.nominal",
        translation_key="ups_power_nominal",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "ups.realpower": SensorEntityDescription(
        key="ups.realpower",
        translation_key="ups_realpower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "ups.realpower.nominal": SensorEntityDescription(
        key="ups.realpower.nominal",
        translation_key="ups_realpower_nominal",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "ups.beeper.status": SensorEntityDescription(
        key="ups.beeper.status",
        translation_key="ups_beeper_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "ups.type": SensorEntityDescription(
        key="ups.type",
        translation_key="ups_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "ups.watchdog.status": SensorEntityDescription(
        key="ups.watchdog.status",
        translation_key="ups_watchdog_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "ups.start.auto": SensorEntityDescription(
        key="ups.start.auto",
        translation_key="ups_start_auto",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "ups.start.battery": SensorEntityDescription(
        key="ups.start.battery",
        translation_key="ups_start_battery",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "ups.start.reboot": SensorEntityDescription(
        key="ups.start.reboot",
        translation_key="ups_start_reboot",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "ups.shutdown": SensorEntityDescription(
        key="ups.shutdown",
        translation_key="ups_shutdown",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "battery.charge": SensorEntityDescription(
        key="battery.charge",
        translation_key="battery_charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "battery.charge.low": SensorEntityDescription(
        key="battery.charge.low",
        translation_key="battery_charge_low",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "battery.charge.restart": SensorEntityDescription(
        key="battery.charge.restart",
        translation_key="battery_charge_restart",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "battery.charge.warning": SensorEntityDescription(
        key="battery.charge.warning",
        translation_key="battery_charge_warning",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "battery.charger.status": SensorEntityDescription(
        key="battery.charger.status",
        translation_key="battery_charger_status",
    ),
    "battery.voltage": SensorEntityDescription(
        key="battery.voltage",
        translation_key="battery_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "battery.voltage.nominal": SensorEntityDescription(
        key="battery.voltage.nominal",
        translation_key="battery_voltage_nominal",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "battery.voltage.low": SensorEntityDescription(
        key="battery.voltage.low",
        translation_key="battery_voltage_low",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "battery.voltage.high": SensorEntityDescription(
        key="battery.voltage.high",
        translation_key="battery_voltage_high",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "battery.capacity": SensorEntityDescription(
        key="battery.capacity",
        translation_key="battery_capacity",
        native_unit_of_measurement="Ah",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "battery.current": SensorEntityDescription(
        key="battery.current",
        translation_key="battery_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "battery.current.total": SensorEntityDescription(
        key="battery.current.total",
        translation_key="battery_current_total",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "battery.temperature": SensorEntityDescription(
        key="battery.temperature",
        translation_key="battery_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "battery.runtime": SensorEntityDescription(
        key="battery.runtime",
        translation_key="battery_runtime",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "battery.runtime.low": SensorEntityDescription(
        key="battery.runtime.low",
        translation_key="battery_runtime_low",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "battery.runtime.restart": SensorEntityDescription(
        key="battery.runtime.restart",
        translation_key="battery_runtime_restart",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "battery.alarm.threshold": SensorEntityDescription(
        key="battery.alarm.threshold",
        translation_key="battery_alarm_threshold",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "battery.date": SensorEntityDescription(
        key="battery.date",
        translation_key="battery_date",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "battery.mfr.date": SensorEntityDescription(
        key="battery.mfr.date",
        translation_key="battery_mfr_date",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "battery.packs": SensorEntityDescription(
        key="battery.packs",
        translation_key="battery_packs",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "battery.packs.bad": SensorEntityDescription(
        key="battery.packs.bad",
        translation_key="battery_packs_bad",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "battery.type": SensorEntityDescription(
        key="battery.type",
        translation_key="battery_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.sensitivity": SensorEntityDescription(
        key="input.sensitivity",
        translation_key="input_sensitivity",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.transfer.low": SensorEntityDescription(
        key="input.transfer.low",
        translation_key="input_transfer_low",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.transfer.high": SensorEntityDescription(
        key="input.transfer.high",
        translation_key="input_transfer_high",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.transfer.reason": SensorEntityDescription(
        key="input.transfer.reason",
        translation_key="input_transfer_reason",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.voltage": SensorEntityDescription(
        key="input.voltage",
        translation_key="input_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "input.voltage.nominal": SensorEntityDescription(
        key="input.voltage.nominal",
        translation_key="input_voltage_nominal",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.L1-N.voltage": SensorEntityDescription(
        key="input.L1-N.voltage",
        translation_key="input_l1_n_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.L2-N.voltage": SensorEntityDescription(
        key="input.L2-N.voltage",
        translation_key="input_l2_n_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.L3-N.voltage": SensorEntityDescription(
        key="input.L3-N.voltage",
        translation_key="input_l3_n_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.frequency": SensorEntityDescription(
        key="input.frequency",
        translation_key="input_frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.frequency.nominal": SensorEntityDescription(
        key="input.frequency.nominal",
        translation_key="input_frequency_nominal",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.frequency.status": SensorEntityDescription(
        key="input.frequency.status",
        translation_key="input_frequency_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.L1.frequency": SensorEntityDescription(
        key="input.L1.frequency",
        translation_key="input_l1_frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.L2.frequency": SensorEntityDescription(
        key="input.L2.frequency",
        translation_key="input_l2_frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.L3.frequency": SensorEntityDescription(
        key="input.L3.frequency",
        translation_key="input_l3_frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.bypass.current": SensorEntityDescription(
        key="input.bypass.current",
        translation_key="input_bypass_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.bypass.L1.current": SensorEntityDescription(
        key="input.bypass.L1.current",
        translation_key="input_bypass_l1_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.bypass.L2.current": SensorEntityDescription(
        key="input.bypass.L2.current",
        translation_key="input_bypass_l2_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.bypass.L3.current": SensorEntityDescription(
        key="input.bypass.L3.current",
        translation_key="input_bypass_l3_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.bypass.frequency": SensorEntityDescription(
        key="input.bypass.frequency",
        translation_key="input_bypass_frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.bypass.phases": SensorEntityDescription(
        key="input.bypass.phases",
        translation_key="input_bypass_phases",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.bypass.realpower": SensorEntityDescription(
        key="input.bypass.realpower",
        translation_key="input_bypass_realpower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.bypass.L1.realpower": SensorEntityDescription(
        key="input.bypass.L1.realpower",
        translation_key="input_bypass_l1_realpower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.bypass.L2.realpower": SensorEntityDescription(
        key="input.bypass.L2.realpower",
        translation_key="input_bypass_l2_realpower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.bypass.L3.realpower": SensorEntityDescription(
        key="input.bypass.L3.realpower",
        translation_key="input_bypass_l3_realpower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.bypass.voltage": SensorEntityDescription(
        key="input.bypass.voltage",
        translation_key="input_bypass_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.bypass.L1-N.voltage": SensorEntityDescription(
        key="input.bypass.L1-N.voltage",
        translation_key="input_bypass_l1_n_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.bypass.L2-N.voltage": SensorEntityDescription(
        key="input.bypass.L2-N.voltage",
        translation_key="input_bypass_l2_n_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.bypass.L3-N.voltage": SensorEntityDescription(
        key="input.bypass.L3-N.voltage",
        translation_key="input_bypass_l3_n_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.current": SensorEntityDescription(
        key="input.current",
        translation_key="input_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "input.L1.current": SensorEntityDescription(
        key="input.L1.current",
        translation_key="input_l1_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.L2.current": SensorEntityDescription(
        key="input.L2.current",
        translation_key="input_l2_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.L3.current": SensorEntityDescription(
        key="input.L3.current",
        translation_key="input_l3_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.phases": SensorEntityDescription(
        key="input.phases",
        translation_key="input_phases",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.realpower": SensorEntityDescription(
        key="input.realpower",
        translation_key="input_realpower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.L1.realpower": SensorEntityDescription(
        key="input.L1.realpower",
        translation_key="input_l1_realpower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.L2.realpower": SensorEntityDescription(
        key="input.L2.realpower",
        translation_key="input_l2_realpower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "input.L3.realpower": SensorEntityDescription(
        key="input.L3.realpower",
        translation_key="input_l3_realpower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "output.power.nominal": SensorEntityDescription(
        key="output.power.nominal",
        translation_key="output_power_nominal",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "output.L1.power.percent": SensorEntityDescription(
        key="output.L1.power.percent",
        translation_key="output_l1_power_percent",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "output.L2.power.percent": SensorEntityDescription(
        key="output.L2.power.percent",
        translation_key="output_l2_power_percent",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "output.L3.power.percent": SensorEntityDescription(
        key="output.L3.power.percent",
        translation_key="output_l3_power_percent",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "output.current": SensorEntityDescription(
        key="output.current",
        translation_key="output_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "output.current.nominal": SensorEntityDescription(
        key="output.current.nominal",
        translation_key="output_current_nominal",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "output.L1.current": SensorEntityDescription(
        key="output.L1.current",
        translation_key="output_l1_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "output.L2.current": SensorEntityDescription(
        key="output.L2.current",
        translation_key="output_l2_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "output.L3.current": SensorEntityDescription(
        key="output.L3.current",
        translation_key="output_l3_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "output.voltage": SensorEntityDescription(
        key="output.voltage",
        translation_key="output_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "output.voltage.nominal": SensorEntityDescription(
        key="output.voltage.nominal",
        translation_key="output_voltage_nominal",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "output.L1-N.voltage": SensorEntityDescription(
        key="output.L1-N.voltage",
        translation_key="output_l1_n_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "output.L2-N.voltage": SensorEntityDescription(
        key="output.L2-N.voltage",
        translation_key="output_l2_n_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "output.L3-N.voltage": SensorEntityDescription(
        key="output.L3-N.voltage",
        translation_key="output_l3_n_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "output.frequency": SensorEntityDescription(
        key="output.frequency",
        translation_key="output_frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "output.frequency.nominal": SensorEntityDescription(
        key="output.frequency.nominal",
        translation_key="output_frequency_nominal",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "output.phases": SensorEntityDescription(
        key="output.phases",
        translation_key="output_phases",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "output.power": SensorEntityDescription(
        key="output.power",
        translation_key="output_power",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "output.realpower": SensorEntityDescription(
        key="output.realpower",
        translation_key="output_realpower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "output.realpower.nominal": SensorEntityDescription(
        key="output.realpower.nominal",
        translation_key="output_realpower_nominal",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "output.L1.realpower": SensorEntityDescription(
        key="output.L1.realpower",
        translation_key="output_l1_realpower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "output.L2.realpower": SensorEntityDescription(
        key="output.L2.realpower",
        translation_key="output_l2_realpower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "output.L3.realpower": SensorEntityDescription(
        key="output.L3.realpower",
        translation_key="output_l3_realpower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "ambient.humidity": SensorEntityDescription(
        key="ambient.humidity",
        translation_key="ambient_humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "ambient.temperature": SensorEntityDescription(
        key="ambient.temperature",
        translation_key="ambient_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "watts": SensorEntityDescription(
        key="watts",
        translation_key="watts",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


def _get_nut_device_info(data: PyNUTData) -> DeviceInfo:
    """Return a DeviceInfo object filled with NUT device info."""
    nut_dev_infos = asdict(data.device_info)
    nut_infos = {
        info_key: nut_dev_infos[nut_key]
        for nut_key, info_key in NUT_DEV_INFO_TO_DEV_INFO.items()
        if nut_dev_infos[nut_key] is not None
    }

    return cast(DeviceInfo, nut_infos)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NutConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the NUT sensors."""

    pynut_data = config_entry.runtime_data
    coordinator = pynut_data.coordinator
    data = pynut_data.data
    unique_id = pynut_data.unique_id
    status = coordinator.data

    resources = [sensor_id for sensor_id in SENSOR_TYPES if sensor_id in status]
    # Display status is a special case that falls back to the status value
    # of the UPS instead.
    if KEY_STATUS in resources:
        resources.append(KEY_STATUS_DISPLAY)

    async_add_entities(
        NUTSensor(
            coordinator,
            SENSOR_TYPES[sensor_type],
            data,
            unique_id,
        )
        for sensor_type in resources
    )


class NUTSensor(CoordinatorEntity[DataUpdateCoordinator[dict[str, str]]], SensorEntity):
    """Representation of a sensor entity for NUT status values."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, str]],
        sensor_description: SensorEntityDescription,
        data: PyNUTData,
        unique_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = sensor_description

        device_name = data.name.title()
        self._attr_unique_id = f"{unique_id}_{sensor_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=device_name,
        )
        self._attr_device_info.update(_get_nut_device_info(data))

    @property
    def native_value(self) -> str | None:
        """Return entity state from ups."""
        status = self.coordinator.data
        if self.entity_description.key == KEY_STATUS_DISPLAY:
            return _format_display_state(status)
        return status.get(self.entity_description.key)


def _format_display_state(status: dict[str, str]) -> str:
    """Return UPS display state."""
    try:
        return " ".join(STATE_TYPES[state] for state in status[KEY_STATUS].split())
    except KeyError:
        return STATE_UNKNOWN
