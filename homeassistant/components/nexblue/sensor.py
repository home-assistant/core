"""Sensors for the NexBlue integration."""

from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NexBlueConfigEntry
from .coordinator import NexBlueDataUpdateCoordinator

DIAGNOSTIC_METRICS = {
    "access_level",
    "brightness",
    "cable_current_limit",
    "cable_lock_mode",
    "circuit_fuse",
    "is_disable",
    "is_lock",
    "network_status",
    "phase_charging",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NexBlueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NexBlue sensors for every discovered charger."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        entity
        for serial_number in coordinator.data
        for entity in (
            NexBlueStatusSensor(coordinator, serial_number, "charging_state"),
            NexBlueStatusSensor(coordinator, serial_number, "is_lock"),
            NexBlueStatusSensor(coordinator, serial_number, "cable_lock_mode"),
            NexBlueStatusSensor(coordinator, serial_number, "is_disable"),
            NexBlueStatusSensor(coordinator, serial_number, "access_level"),
            NexBlueStatusSensor(coordinator, serial_number, "phase_charging"),
            NexBlueStatusSensor(coordinator, serial_number, "power"),
            NexBlueStatusSensor(coordinator, serial_number, "energy"),
            NexBlueStatusSensor(coordinator, serial_number, "lifetime_energy"),
            NexBlueStatusSensor(coordinator, serial_number, "current_limit"),
            NexBlueStatusSensor(coordinator, serial_number, "cable_current_limit"),
            NexBlueStatusSensor(coordinator, serial_number, "circuit_fuse"),
            *(
                NexBlueStatusSensor(coordinator, serial_number, "current", phase)
                for phase in range(3)
            ),
            *(
                NexBlueStatusSensor(coordinator, serial_number, "voltage", phase)
                for phase in range(3)
            ),
            NexBlueStatusSensor(coordinator, serial_number, "network_status"),
            NexBlueStatusSensor(coordinator, serial_number, "brightness"),
        )
    )


class NexBlueStatusSensor(
    CoordinatorEntity[NexBlueDataUpdateCoordinator], SensorEntity
):
    """Expose normalized NexBlue charger telemetry."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NexBlueDataUpdateCoordinator,
        serial_number: str,
        metric: str,
        phase: int | None = None,
    ) -> None:
        """Initialize a sensor for one charger metric."""
        super().__init__(coordinator)
        self._serial_number = serial_number
        self._metric = metric
        self._phase = phase

        suffix = f"_{phase + 1}" if phase is not None else ""
        self._attr_unique_id = f"{serial_number}_{metric}{suffix}"
        self._attr_translation_key = f"{metric}{suffix}"
        self._attr_icon = _sensor_icon(metric)
        self._attr_device_info = DeviceInfo(
            identifiers={("nexblue", serial_number)},
            manufacturer="NexBlue",
            name=serial_number,
        )

        if metric in DIAGNOSTIC_METRICS:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

        if metric == "power":
            self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif metric == "energy":
            self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_state_class = SensorStateClass.TOTAL
        elif metric == "lifetime_energy":
            self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif metric in {
            "current",
            "current_limit",
            "cable_current_limit",
            "circuit_fuse",
        }:
            self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
            self._attr_device_class = SensorDeviceClass.CURRENT
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif metric == "voltage":
            self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
            self._attr_device_class = SensorDeviceClass.VOLTAGE
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif metric == "brightness":
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    @override
    def available(self) -> bool:
        """Return whether this charger is currently reachable."""
        return (
            super().available
            and self.coordinator.data.get(self._serial_number) is not None
        )

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value from the latest coordinator data."""
        status = self.coordinator.data.get(self._serial_number)
        if status is None:
            return None

        if self._metric == "charging_state":
            return CHARGING_STATE_MAP.get(
                status.charging_state, f"Unknown ({status.charging_state})"
            )
        if self._metric == "network_status":
            return NETWORK_STATUS_MAP.get(
                status.network_status, f"Unknown ({status.network_status})"
            )
        if self._metric == "is_disable":
            return _bool_text(
                status.is_disable, true_text="Disabled", false_text="Enabled"
            )
        if self._metric == "is_lock":
            return _bool_text(status.is_lock, true_text="Locked", false_text="Unlocked")
        if self._metric == "power":
            return status.power_kw
        if self._metric == "energy":
            return status.energy_kwh
        if self._metric == "lifetime_energy":
            return status.lifetime_energy_kwh
        if self._metric == "current_limit":
            return status.current_limit_a
        if self._metric == "cable_current_limit":
            return status.cable_current_limit_a
        if self._metric == "circuit_fuse":
            return status.circuit_fuse_a
        if self._metric == "cable_lock_mode":
            return CABLE_LOCK_MODE_MAP.get(
                status.cable_lock_mode, f"Unknown ({status.cable_lock_mode})"
            )
        if self._metric == "access_level":
            return ACCESS_LEVEL_MAP.get(
                status.access_level, f"Unknown ({status.access_level})"
            )
        if self._metric == "phase_charging":
            return PHASE_CHARGING_MAP.get(
                status.phase_charging, f"Unknown ({status.phase_charging})"
            )
        if self._metric == "brightness":
            return status.brightness_percent

        values = status.current_a if self._metric == "current" else status.voltage_v
        if self._phase is None or len(values) <= self._phase:
            return None
        return values[self._phase]


CHARGING_STATE_MAP = {
    0: "Connect cable to charge",
    1: "Ready to charge",
    2: "Charging",
    3: "Charging complete",
    4: "Charging unavailable",
    5: "Waiting for available power",
    6: "Schedule waiting",
    7: "Waiting for car response",
}

NETWORK_STATUS_MAP = {
    0: "None",
    1: "Wi-Fi",
    2: "4G",
    3: "Ethernet",
}

CABLE_LOCK_MODE_MAP = {
    0: "Locked while charging",
    1: "Always locked",
}

ACCESS_LEVEL_MAP = {
    0: "Authorized users only",
    1: "No restrictions",
}

PHASE_CHARGING_MAP = {
    0: "Three-phase",
    1: "Single-phase",
}


def _bool_text(value: bool | None, *, true_text: str, false_text: str) -> str | None:
    """Return a friendly text value for an optional boolean."""
    if value is None:
        return None
    return true_text if value else false_text


def _sensor_icon(metric: str) -> str | None:
    """Return a suitable Material Design Icon for a metric."""
    if metric == "charging_state":
        return "mdi:ev-station"
    if metric == "network_status":
        return "mdi:network-outline"
    if metric == "is_disable":
        return "mdi:check-circle-outline"
    if metric == "is_lock":
        return "mdi:lock-check"
    if metric == "power":
        return "mdi:flash"
    if metric == "energy":
        return "mdi:lightning-bolt"
    if metric == "lifetime_energy":
        return "mdi:counter"
    if metric in {"current", "current_limit", "cable_current_limit"}:
        return "mdi:current-ac"
    if metric == "circuit_fuse":
        return "mdi:fuse"
    if metric == "cable_lock_mode":
        return "mdi:lock-clock"
    if metric == "access_level":
        return "mdi:account-lock"
    if metric in {"phase_charging", "voltage"}:
        return "mdi:sine-wave"
    if metric == "brightness":
        return "mdi:brightness-percent"
    return None
