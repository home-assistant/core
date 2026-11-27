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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    NexBlueConfigEntry,
    NexBlueDataUpdateCoordinator,
    NexBlueSmartMeterCoordinator,
    SmartMeterData,
)
from .entity import charger_device_info

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
class NexBlueChargerSensorEntityDescription(SensorEntityDescription):
    """Describe a NexBlue charger sensor."""

    value_fn: Callable[[ChargerStatus], StateType]
    phase: int | None = None


@dataclass(frozen=True, kw_only=True)
class NexBlueSmartMeterSensorEntityDescription(SensorEntityDescription):
    """Describe a Smart Meter sensor."""

    value_fn: Callable[[SmartMeterData], StateType]


def _smart_meter_energy_fn(period: str) -> Callable[[SmartMeterData], StateType]:
    """Return a typed reader for a Smart Meter consumption period."""

    def value_fn(data: SmartMeterData) -> StateType:
        return getattr(data, period)

    return value_fn


SMART_METER_SENSORS = tuple(
    NexBlueSmartMeterSensorEntityDescription(
        key=f"household_consumption_{period}",
        translation_key=f"household_consumption_{period}",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=_smart_meter_energy_fn(period),
    )
    for period in ("today", "month", "year")
)


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


SENSOR_DESCRIPTIONS: tuple[NexBlueChargerSensorEntityDescription, ...] = (
    NexBlueChargerSensorEntityDescription(
        key="charging_state",
        translation_key="charging_state",
        device_class=SensorDeviceClass.ENUM,
        options=_enum_options(CHARGING_STATE_MAP),
        value_fn=lambda status: CHARGING_STATE_MAP.get(status.charging_state),
    ),
    NexBlueChargerSensorEntityDescription(
        key="cable_lock_mode",
        translation_key="cable_lock_mode",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=_enum_options(CABLE_LOCK_MODE_MAP),
        value_fn=lambda status: (
            CABLE_LOCK_MODE_MAP.get(status.cable_lock_mode)
            if status.cable_lock_mode is not None
            else None
        ),
    ),
    NexBlueChargerSensorEntityDescription(
        key="access_level",
        translation_key="access_level",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=_enum_options(ACCESS_LEVEL_MAP),
        value_fn=lambda status: (
            ACCESS_LEVEL_MAP.get(status.access_level)
            if status.access_level is not None
            else None
        ),
    ),
    NexBlueChargerSensorEntityDescription(
        key="phase_charging",
        translation_key="phase_charging",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=_enum_options(PHASE_CHARGING_MAP),
        value_fn=lambda status: (
            PHASE_CHARGING_MAP.get(status.phase_charging)
            if status.phase_charging is not None
            else None
        ),
    ),
    NexBlueChargerSensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.power_kw,
    ),
    NexBlueChargerSensorEntityDescription(
        key="energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda status: status.energy_kwh,
    ),
    NexBlueChargerSensorEntityDescription(
        key="lifetime_energy",
        translation_key="lifetime_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda status: status.lifetime_energy_kwh,
    ),
    NexBlueChargerSensorEntityDescription(
        key="current_limit",
        translation_key="current_limit",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.current_limit_a,
    ),
    NexBlueChargerSensorEntityDescription(
        key="cable_current_limit",
        translation_key="cable_current_limit",
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.cable_current_limit_a,
    ),
    NexBlueChargerSensorEntityDescription(
        key="circuit_fuse",
        translation_key="circuit_fuse",
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.circuit_fuse_a,
    ),
    *(
        NexBlueChargerSensorEntityDescription(
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
        NexBlueChargerSensorEntityDescription(
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
    NexBlueChargerSensorEntityDescription(
        key="network_status",
        translation_key="network_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=_enum_options(NETWORK_STATUS_MAP),
        value_fn=lambda status: (
            NETWORK_STATUS_MAP.get(status.network_status)
            if status.network_status is not None
            else None
        ),
    ),
    NexBlueChargerSensorEntityDescription(
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
    meter_coordinator = NexBlueSmartMeterCoordinator(hass, entry, coordinator)
    await meter_coordinator.async_refresh()
    known_meters: set[str] = set()

    @callback
    def add_new_meters() -> None:
        """Create entities when supported meters become available."""
        entities: list[NexBlueSmartMeterSensor] = []
        for serial_number, data in (meter_coordinator.data or {}).items():
            if data is None or serial_number in known_meters:
                continue
            known_meters.add(serial_number)
            entities.extend(
                NexBlueSmartMeterSensor(
                    meter_coordinator, serial_number, description, data
                )
                for description in SMART_METER_SENSORS
            )
        async_add_entities(entities)

    add_new_meters()
    entry.async_on_unload(meter_coordinator.async_add_listener(add_new_meters))


class NexBlueSmartMeterSensor(
    CoordinatorEntity[NexBlueSmartMeterCoordinator], SensorEntity
):
    """Expose one Smart Meter measurement."""

    _attr_has_entity_name = True
    entity_description: NexBlueSmartMeterSensorEntityDescription

    def __init__(
        self,
        coordinator: NexBlueSmartMeterCoordinator,
        serial_number: str,
        description: NexBlueSmartMeterSensorEntityDescription,
        data: SmartMeterData,
    ) -> None:
        """Initialize a Smart Meter entity."""
        super().__init__(coordinator)
        self._serial_number = serial_number
        self.entity_description = description
        self._attr_unique_id = f"{serial_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            manufacturer="NexBlue",
            name=data.device.name or serial_number,
            serial_number=serial_number,
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether statistics for this meter are available."""
        return (
            super().available
            and self.coordinator.data.get(self._serial_number) is not None
        )

    @property
    @override
    def native_value(self) -> StateType:
        """Return the latest recorded measurement."""
        data = self.coordinator.data.get(self._serial_number)
        return self.entity_description.value_fn(data) if data is not None else None


class NexBlueStatusSensor(
    CoordinatorEntity[NexBlueDataUpdateCoordinator], SensorEntity
):
    """Expose normalized NexBlue charger telemetry."""

    _attr_has_entity_name = True
    entity_description: NexBlueChargerSensorEntityDescription

    def __init__(
        self,
        coordinator: NexBlueDataUpdateCoordinator,
        serial_number: str,
        description: NexBlueChargerSensorEntityDescription,
    ) -> None:
        """Initialize a sensor for one charger metric."""
        super().__init__(coordinator)
        self._serial_number = serial_number
        self.entity_description = description
        self._attr_unique_id = f"{serial_number}_{description.key}"
        if description.phase is not None:
            self._attr_translation_placeholders = {"phase": f"L{description.phase}"}
        self._attr_device_info = charger_device_info(serial_number)

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
