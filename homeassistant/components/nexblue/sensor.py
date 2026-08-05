"""Sensors for the NexBlue integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from nexblue_api.models import ChargerStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
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

from .coordinator import NexBlueConfigEntry, NexBlueDataUpdateCoordinator


def _enum_value(values: dict[int, str], value: int | None) -> str | None:
    """Return a known text value or a safe fallback for a protocol value."""
    if value is None:
        return None
    return values.get(value, f"Unknown ({value})")


def _bool_value(value: bool | None, *, true_value: str, false_value: str) -> str | None:
    """Return a text value for an optional boolean."""
    if value is None:
        return None
    return true_value if value else false_value


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

NETWORK_STATUS_MAP = {0: "None", 1: "Wi-Fi", 2: "4G", 3: "Ethernet"}

CABLE_LOCK_MODE_MAP = {0: "Locked while charging", 1: "Always locked"}

ACCESS_LEVEL_MAP = {0: "Authorized users only", 1: "No restrictions"}

PHASE_CHARGING_MAP = {0: "Three-phase", 1: "Single-phase"}


@dataclass(frozen=True, kw_only=True)
class NexBlueSensorEntityDescription(SensorEntityDescription):
    """Describe a NexBlue charger sensor."""

    value_fn: Callable[[ChargerStatus], StateType]


SENSOR_DESCRIPTIONS: tuple[NexBlueSensorEntityDescription, ...] = (
    NexBlueSensorEntityDescription(
        key="charging_state",
        translation_key="charging_state",
        value_fn=lambda status: _enum_value(CHARGING_STATE_MAP, status.charging_state),
    ),
    NexBlueSensorEntityDescription(
        key="is_lock",
        translation_key="is_lock",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: _bool_value(
            status.is_lock, true_value="Locked", false_value="Unlocked"
        ),
    ),
    NexBlueSensorEntityDescription(
        key="cable_lock_mode",
        translation_key="cable_lock_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: _enum_value(
            CABLE_LOCK_MODE_MAP, status.cable_lock_mode
        ),
    ),
    NexBlueSensorEntityDescription(
        key="is_disable",
        translation_key="is_disable",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: _bool_value(
            status.is_disable, true_value="Disabled", false_value="Enabled"
        ),
    ),
    NexBlueSensorEntityDescription(
        key="access_level",
        translation_key="access_level",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: _enum_value(ACCESS_LEVEL_MAP, status.access_level),
    ),
    NexBlueSensorEntityDescription(
        key="phase_charging",
        translation_key="phase_charging",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: _enum_value(PHASE_CHARGING_MAP, status.phase_charging),
    ),
    NexBlueSensorEntityDescription(
        key="power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.power_kw,
    ),
    NexBlueSensorEntityDescription(
        key="energy",
        translation_key="energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda status: status.energy_kwh,
    ),
    NexBlueSensorEntityDescription(
        key="lifetime_energy",
        translation_key="lifetime_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda status: status.lifetime_energy_kwh,
    ),
    NexBlueSensorEntityDescription(
        key="current_limit",
        translation_key="current_limit",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.current_limit_a,
    ),
    NexBlueSensorEntityDescription(
        key="cable_current_limit",
        translation_key="cable_current_limit",
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.cable_current_limit_a,
    ),
    NexBlueSensorEntityDescription(
        key="circuit_fuse",
        translation_key="circuit_fuse",
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.circuit_fuse_a,
    ),
    *(
        NexBlueSensorEntityDescription(
            key=f"current_{phase}",
            translation_key=f"current_{phase}",
            device_class=SensorDeviceClass.CURRENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=value_fn,
        )
        for phase, value_fn in (
            (1, lambda status: status.current_a[0]),
            (2, lambda status: status.current_a[1]),
            (3, lambda status: status.current_a[2]),
        )
    ),
    *(
        NexBlueSensorEntityDescription(
            key=f"voltage_{phase}",
            translation_key=f"voltage_{phase}",
            device_class=SensorDeviceClass.VOLTAGE,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=value_fn,
        )
        for phase, value_fn in (
            (1, lambda status: status.voltage_v[0]),
            (2, lambda status: status.voltage_v[1]),
            (3, lambda status: status.voltage_v[2]),
        )
    ),
    NexBlueSensorEntityDescription(
        key="network_status",
        translation_key="network_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: _enum_value(NETWORK_STATUS_MAP, status.network_status),
    ),
    NexBlueSensorEntityDescription(
        key="brightness",
        translation_key="brightness",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.brightness_percent,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NexBlueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NexBlue sensors for every discovered charger."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        NexBlueStatusSensor(coordinator, serial_number, description)
        for serial_number in coordinator.data
        for description in SENSOR_DESCRIPTIONS
    )


class NexBlueStatusSensor(
    CoordinatorEntity[NexBlueDataUpdateCoordinator], SensorEntity
):
    """Expose normalized NexBlue charger telemetry."""

    _attr_has_entity_name = True
    entity_description: NexBlueSensorEntityDescription

    def __init__(
        self,
        coordinator: NexBlueDataUpdateCoordinator,
        serial_number: str,
        description: NexBlueSensorEntityDescription,
    ) -> None:
        """Initialize a sensor for one charger metric."""
        super().__init__(coordinator)
        self._serial_number = serial_number
        self.entity_description = description
        self._attr_unique_id = f"{serial_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={("nexblue", serial_number)},
            manufacturer="NexBlue",
            name=serial_number,
        )

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
        return self.entity_description.value_fn(status)
