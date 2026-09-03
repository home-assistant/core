"""Sensor platform for Besen."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final, override

from besen.models import BesenData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BesenConfigEntry
from .coordinator import BesenCoordinator
from .entity import BesenEntity

PARALLEL_UPDATES = 0

ERROR_STATES: Final = {
    "Relay Stick Error": "relay_stick_error",
    "OFFLINE": "offline",
    "CC Error": "cc_error",
    "CP Error": "cp_error",
    "Emergency Stop": "emergency_stop",
    "Over Temperature": "over_temperature",
    "Unknown": "unknown",
    "Leakage Protection": "leakage_protection",
    "Short Circuit": "short_circuit",
    "Over Current": "over_current",
    "Ungrounded": "ungrounded",
    "Over Voltage": "over_voltage",
    "Low Voltage": "low_voltage",
    "Input Power Error": "input_power_error",
    "DLB Over Current - Mains overload": "dlb_over_current",
    "Diode Short Circuit": "diode_short_circuit",
    "RTC Failure": "rtc_failure",
    "Flash Memory Failure": "flash_memory_failure",
    "EEPROM Failure": "eeprom_failure",
    "Metering Module Failure": "metering_module_failure",
    "No Error": "no_error",
}

CHARGING_STATES: Final = {
    "Start": "start",
    "Finish Charging": "finish_charging",
    "Waiting": "waiting",
    "Finished": "finished",
    "Cancel": "canceled",
    "Connect": "connect",
    "Fault": "fault",
}

CHARGING_MESSAGES: Final = {
    "EV is connected, please press start": "ev_connected_press_start",
    "Charging": "charging",
    "Charging has started, waiting for EV.": "waiting_for_ev",
    "Charging completed": "charging_completed",
    "Charging reservation.": "charging_reservation",
    "The plug is not connected, please start charging after connecting.": (
        "plug_not_connected"
    ),
    "See Error State": "see_error_state",
    "Wait for the swipe to start": "waiting_for_swipe",
    "Wait for the button to activate": "waiting_for_button",
}

PLUG_STATES: Final = {
    "Unknown 0": "unknown_0",
    "Disconnected": "disconnected",
    "Connected Unlocked": "connected_unlocked",
    "Unknown 1": "unknown_1",
    "Connected Locked": "connected_locked",
    "Unknown 2": "unknown_2",
    "Unknown 3": "unknown_3",
    "Unknown 4": "unknown_4",
    "Unknown 5": "unknown_5",
}

OUTPUT_STATES: Final = {
    "Unknown 0": "unknown_0",
    "Charging": "charging",
    "Idle": "idle",
    "Unknown 1": "unknown_1",
    "Unknown 2": "unknown_2",
    "Unknown 3": "unknown_3",
    "Unknown 4": "unknown_4",
    "Unknown 5": "unknown_5",
    "Unknown 6": "unknown_6",
}

CURRENT_STATES: Final = {
    "Fault": "fault",
    "Charging Fault 1": "charging_fault_1",
    "Charging Fault 2": "charging_fault_2",
    "Unknown 1": "unknown_1",
    "Unknown 2": "unknown_2",
    "Unknown 3": "unknown_3",
    "Unknown 4": "unknown_4",
    "Unknown 5": "unknown_5",
    "Unknown 6": "unknown_6",
    "Waiting for swipe": "waiting_for_swipe",
    "Waiting for button": "waiting_for_button",
    "Not Connected": "not_connected",
    "Ready to charge": "ready_to_charge",
    "Charging": "charging",
    "Completed": "completed",
    "Unknown 7": "unknown_7",
    "Completed Full Charge": "completed_full_charge",
    "Unknown 8": "unknown_8",
    "Unknown 9": "unknown_9",
    "Charging Reservation": "charging_reservation",
    "Unknown 10": "unknown_10",
}


def _enum_state(value: str | None, states: Mapping[str, str]) -> str | None:
    """Return the stable Home Assistant value for a charger state."""

    return states.get(value) if value is not None else None


@dataclass(frozen=True, kw_only=True)
class BesenSensorEntityDescription(SensorEntityDescription):
    """Describe a Besen sensor entity."""

    value_fn: Callable[[BesenData], StateType]
    three_phase_only: bool = False


SENSOR_DESCRIPTIONS: tuple[BesenSensorEntityDescription, ...] = (
    BesenSensorEntityDescription(
        key="charging_status",
        translation_key="charging_status",
        device_class=SensorDeviceClass.ENUM,
        options=list(CHARGING_STATES.values()),
        value_fn=lambda data: _enum_state(data.charge.charging_status, CHARGING_STATES),
    ),
    BesenSensorEntityDescription(
        key="charging_message",
        translation_key="charging_message",
        device_class=SensorDeviceClass.ENUM,
        options=list(CHARGING_MESSAGES.values()),
        value_fn=lambda data: _enum_state(
            data.charge.charging_status_description, CHARGING_MESSAGES
        ),
    ),
    BesenSensorEntityDescription(
        key="error_state",
        translation_key="error_state",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        options=list(ERROR_STATES.values()),
        value_fn=lambda data: _enum_state(data.charge.error_details, ERROR_STATES),
    ),
    BesenSensorEntityDescription(
        key="plug_state",
        translation_key="plug_state",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        options=list(PLUG_STATES.values()),
        value_fn=lambda data: _enum_state(data.charge.plug_state, PLUG_STATES),
    ),
    BesenSensorEntityDescription(
        key="output_state",
        translation_key="output_state",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        options=list(OUTPUT_STATES.values()),
        value_fn=lambda data: _enum_state(data.charge.output_state, OUTPUT_STATES),
    ),
    BesenSensorEntityDescription(
        key="current_state",
        translation_key="current_state",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        options=list(CURRENT_STATES.values()),
        value_fn=lambda data: _enum_state(data.charge.current_state, CURRENT_STATES),
    ),
    BesenSensorEntityDescription(
        key="charging_power",
        translation_key="charging_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.charge.power,
    ),
    BesenSensorEntityDescription(
        key="total_energy",
        translation_key="total_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: data.charge.total_energy,
    ),
    BesenSensorEntityDescription(
        key="session_energy",
        translation_key="session_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: data.charge.session_energy,
    ),
    BesenSensorEntityDescription(
        key="internal_temperature",
        translation_key="internal_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.charge.inner_temp_c,
    ),
    BesenSensorEntityDescription(
        key="external_temperature",
        translation_key="external_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.charge.outer_temp,
    ),
    BesenSensorEntityDescription(
        key="l1_voltage",
        translation_key="l1_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.charge.l1_voltage,
    ),
    BesenSensorEntityDescription(
        key="l1_current",
        translation_key="l1_current",
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.charge.l1_amperage,
    ),
    BesenSensorEntityDescription(
        key="l2_voltage",
        translation_key="l2_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        three_phase_only=True,
        value_fn=lambda data: data.charge.l2_voltage,
    ),
    BesenSensorEntityDescription(
        key="l2_current",
        translation_key="l2_current",
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        three_phase_only=True,
        value_fn=lambda data: data.charge.l2_amperage,
    ),
    BesenSensorEntityDescription(
        key="l3_voltage",
        translation_key="l3_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        three_phase_only=True,
        value_fn=lambda data: data.charge.l3_voltage,
    ),
    BesenSensorEntityDescription(
        key="l3_current",
        translation_key="l3_current",
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        three_phase_only=True,
        value_fn=lambda data: data.charge.l3_amperage,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BesenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Besen sensors."""

    coordinator = entry.runtime_data
    async_add_entities(
        BesenSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
        if not description.three_phase_only or coordinator.data.info.phases == 3
    )


class BesenSensor(BesenEntity, SensorEntity):
    """Representation of a Besen sensor."""

    entity_description: BesenSensorEntityDescription

    def __init__(
        self,
        coordinator: BesenCoordinator,
        description: BesenSensorEntityDescription,
    ) -> None:
        """Initialize a Besen sensor."""

        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value."""

        return self.entity_description.value_fn(self.coordinator.data)
