"""Sensors for the NexBlue integration."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal, override

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

from .const import DOMAIN
from .coordinator import NexBlueConfigEntry, NexBlueDataUpdateCoordinator

CHARGING_STATE_MAP = {
    0: "idle",
    1: "connected",
    2: "charging",
    3: "finished",
    4: "error",
    5: "lb_waiting",
    6: "delay_waiting",
    7: "ev_waiting",
}

NETWORK_STATUS_MAP = {0: "none", 1: "wifi", 2: "modem", 3: "ethernet"}

CABLE_LOCK_MODE_MAP = {
    0: "locked_while_charging",
    1: "always_locked",
}

ACCESS_LEVEL_MAP = {
    0: "authorized_users_only",
    1: "no_restrictions",
}

PHASE_CHARGING_MAP = {0: "three_phase", 1: "single_phase"}


@dataclass(frozen=True, kw_only=True)
class NexBlueSensorEntityDescription(SensorEntityDescription):
    """Describe a NexBlue charger sensor."""

    value_fn: Callable[[ChargerStatus], StateType]
    phase: int | None = None


def _enum_options(values: dict[int, str]) -> list[str]:
    """Return the supported options for an enum sensor."""
    return list(values.values())


def _phase_value(
    values: Sequence[int | float],
    phase: int,
) -> int | float | None:
    """Return a phase value when it is reported by the charger."""
    if len(values) <= phase:
        return None
    return values[phase]


def _phase_value_fn(
    metric: Literal["current", "voltage"], phase: int
) -> Callable[[ChargerStatus], StateType]:
    """Return a typed value function for a phase measurement."""

    def value_fn(status: ChargerStatus) -> StateType:
        values = status.current_a if metric == "current" else status.voltage_v
        return _phase_value(values, phase)

    return value_fn


SENSOR_DESCRIPTIONS: tuple[NexBlueSensorEntityDescription, ...] = (
    NexBlueSensorEntityDescription(
        key="charging_state",
        translation_key="charging_state",
        device_class=SensorDeviceClass.ENUM,
        options=_enum_options(CHARGING_STATE_MAP),
        value_fn=lambda status: CHARGING_STATE_MAP.get(status.charging_state),
    ),
    NexBlueSensorEntityDescription(
        key="cable_lock_mode",
        translation_key="cable_lock_mode",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=_enum_options(CABLE_LOCK_MODE_MAP),
        value_fn=lambda status: CABLE_LOCK_MODE_MAP.get(status.cable_lock_mode),
    ),
    NexBlueSensorEntityDescription(
        key="access_level",
        translation_key="access_level",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=_enum_options(ACCESS_LEVEL_MAP),
        value_fn=lambda status: ACCESS_LEVEL_MAP.get(status.access_level),
    ),
    NexBlueSensorEntityDescription(
        key="phase_charging",
        translation_key="phase_charging",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=_enum_options(PHASE_CHARGING_MAP),
        value_fn=lambda status: PHASE_CHARGING_MAP.get(status.phase_charging),
    ),
    NexBlueSensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.power_kw,
    ),
    NexBlueSensorEntityDescription(
        key="energy",
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
            translation_key="current",
            phase=phase,
            device_class=SensorDeviceClass.CURRENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=_phase_value_fn("current", phase - 1),
        )
        for phase in range(1, 4)
    ),
    *(
        NexBlueSensorEntityDescription(
            key=f"voltage_{phase}",
            translation_key="voltage",
            phase=phase,
            device_class=SensorDeviceClass.VOLTAGE,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=_phase_value_fn("voltage", phase - 1),
        )
        for phase in range(1, 4)
    ),
    NexBlueSensorEntityDescription(
        key="network_status",
        translation_key="network_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=_enum_options(NETWORK_STATUS_MAP),
        value_fn=lambda status: NETWORK_STATUS_MAP.get(status.network_status),
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
    coordinator = entry.runtime_data
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
        if description.phase is not None:
            self._attr_translation_placeholders = {"phase": f"L{description.phase}"}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            manufacturer="NexBlue",
            name=serial_number,
            serial_number=serial_number,
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
        status = self.coordinator.data[self._serial_number]
        assert status is not None
        return self.entity_description.value_fn(status)
