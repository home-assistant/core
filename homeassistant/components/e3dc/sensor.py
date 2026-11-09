"""Support for E3/DC sensors."""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import IntEnum
from operator import attrgetter
from typing import TYPE_CHECKING, override

from e3dc_ess_modbus import (
    E3dcPowerStation,
    EmergencyPowerStatus,
    InverterMode,
    PowerMeterReading,
    PowerMeterType,
    SgReadyStatus,
)
from e3dc_ess_modbus.inverter import Inverter

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactivePower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import PartKind
from .coordinator import E3dcConfigEntry, E3dcDataUpdateCoordinator
from .entity import E3dcEntity, E3dcPart

PARALLEL_UPDATES = 0

PHASES = ("l1", "l2", "l3")
# The manual marks DC tracker 3 as not used, but the E3/DC one reports it
DC_TRACKERS = (1, 2, 3)


def _enum_options(enum_type: type[IntEnum]) -> list[str]:
    """The sensor options a device enum maps to."""
    return [member.name.lower() for member in enum_type]


@dataclass(frozen=True, kw_only=True)
class E3dcSensorDescription(SensorEntityDescription):
    """Describe an E3/DC sensor."""

    # The attribute of E3dcPowerStation the sensor reads, e.g. 'power'
    component: str
    value_fn: Callable[[E3dcPowerStation], StateType | IntEnum]
    exists_fn: Callable[[E3dcPowerStation], bool] = lambda _: True


def _has_wallbox(device: E3dcPowerStation) -> bool:
    """Whether a wallbox is configured."""
    return bool(device.wallboxes.configured)


def _has_additional_feeder(device: E3dcPowerStation) -> bool:
    """Whether a power meter measures an additional feeder, e.g. a second PV inverter."""
    return any(
        meter.meter_type
        in (PowerMeterType.EXTERNAL_PRODUCTION, PowerMeterType.EXTERNAL_FARM)
        for meter in device.power_meter_readings.values()
    )


def _grid_meter(device: E3dcPowerStation) -> PowerMeterReading | None:
    """The power meter at the grid connection point, if one is configured."""
    return next(
        (
            meter
            for meter in device.power_meter_readings.values()
            if meter.meter_type is PowerMeterType.ROOT
        ),
        None,
    )


def _grid_phase_power(phase: str) -> Callable[[E3dcPowerStation], StateType]:
    """Read the power on ``phase`` at the grid connection point."""
    get = attrgetter(f"power_{phase}")
    return lambda device: (
        get(meter) if (meter := _grid_meter(device)) is not None else None
    )


def _power(
    key: str,
    value_fn: Callable[[E3dcPowerStation], int | None],
    exists_fn: Callable[[E3dcPowerStation], bool] = lambda _: True,
) -> E3dcSensorDescription:
    """A power flow sensor, in watts."""
    return E3dcSensorDescription(
        key=key,
        translation_key=key,
        component="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=value_fn,
        exists_fn=exists_fn,
    )


SENSORS: tuple[E3dcSensorDescription, ...] = (
    _power("pv_power", lambda device: device.power.pv_power),
    _power(
        "battery_power",
        # E3/DC reports charging as positive power
        # Negate it because Home Assistant expects discharging as positive
        lambda device: (
            None if (power := device.power.battery_power) is None else -power
        ),
    ),
    _power("house_power", lambda device: device.power.house_power),
    _power("grid_power", lambda device: device.power.grid_power),
    *(
        E3dcSensorDescription(
            key=f"grid_power_{phase}",
            translation_key="grid_power_phase",
            translation_placeholders={"phase": phase.upper()},
            component="power_meters",
            device_class=SensorDeviceClass.POWER,
            native_unit_of_measurement=UnitOfPower.WATT,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
            value_fn=_grid_phase_power(phase),
            exists_fn=lambda device: _grid_meter(device) is not None,
        )
        for phase in PHASES
    ),
    _power(
        "additional_power",
        lambda device: device.power.additional_power,
        _has_additional_feeder,
    ),
    _power("wallbox_power", lambda device: device.power.wallbox_power, _has_wallbox),
    _power(
        "wallbox_solar_power",
        lambda device: device.power.wallbox_solar_power,
        _has_wallbox,
    ),
    E3dcSensorDescription(
        key="battery_soc",
        component="power",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.power.battery_soc,
    ),
    E3dcSensorDescription(
        key="autarky",
        translation_key="autarky",
        component="power",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.power.autarky,
    ),
    E3dcSensorDescription(
        key="self_consumption",
        translation_key="self_consumption",
        component="power",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.power.self_consumption,
    ),
    E3dcSensorDescription(
        key="emergency_power_status",
        translation_key="emergency_power_status",
        component="power",
        device_class=SensorDeviceClass.ENUM,
        options=_enum_options(EmergencyPowerStatus),
        value_fn=lambda device: device.power.emergency_power_status,
        exists_fn=lambda device: (
            device.power.emergency_power_status
            is not EmergencyPowerStatus.NOT_SUPPORTED
        ),
    ),
    E3dcSensorDescription(
        key="max_charge_power",
        translation_key="max_charge_power",
        component="battery_limits",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: (
            limits.max_charge_power
            if (limits := device.battery_limits) is not None
            else None
        ),
    ),
    E3dcSensorDescription(
        key="max_discharge_power",
        translation_key="max_discharge_power",
        component="battery_limits",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: (
            limits.max_discharge_power
            if (limits := device.battery_limits) is not None
            else None
        ),
    ),
    E3dcSensorDescription(
        key="remaining_energy",
        component="battery_limits",
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: (
            limits.remaining_energy
            if (limits := device.battery_limits) is not None
            else None
        ),
    ),
    E3dcSensorDescription(
        key="full_charge_energy",
        translation_key="full_charge_energy",
        component="battery_limits",
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: (
            limits.full_charge_energy
            if (limits := device.battery_limits) is not None
            else None
        ),
    ),
    E3dcSensorDescription(
        key="sg_ready_status",
        translation_key="sg_ready_status",
        component="wide_power_meters",
        device_class=SensorDeviceClass.ENUM,
        options=_enum_options(SgReadyStatus),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (
            meters.sg_ready_status
            if (meters := device.wide_power_meters) is not None
            else None
        ),
    ),
    E3dcSensorDescription(
        key="active_power_failsafe_timeout",
        translation_key="active_power_failsafe_timeout",
        component="grid_control",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (
            grid.active_power_failsafe_timeout
            if (grid := device.grid_control) is not None
            else None
        ),
    ),
    E3dcSensorDescription(
        key="reactive_power_failsafe_timeout",
        translation_key="reactive_power_failsafe_timeout",
        component="grid_control",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (
            grid.reactive_power_failsafe_timeout
            if (grid := device.grid_control) is not None
            else None
        ),
    ),
    E3dcSensorDescription(
        key="inverter_mode",
        translation_key="inverter_mode",
        component="inverter_mode_control",
        device_class=SensorDeviceClass.ENUM,
        options=_enum_options(InverterMode),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: (
            mode.inverter_mode
            if (mode := device.inverter_mode_control) is not None
            else None
        ),
    ),
)


@dataclass(frozen=True, kw_only=True)
class E3dcPartSensorDescription(SensorEntityDescription):
    """Describe a sensor of a power meter or an inverter."""

    value_fn: Callable[[E3dcPowerStation, int], StateType | IntEnum]


def _meter_phase_power(phase: str) -> Callable[[E3dcPowerStation, int], StateType]:
    """Read the power on ``phase`` of a power meter slot."""
    get = attrgetter(f"power_{phase}")
    return lambda device, number: get(device.power_meter_readings[number])


def _total(meter: PowerMeterReading) -> int | None:
    """The sum of the meter's phase powers, or ``None`` if any is unknown."""
    powers = (meter.power_l1, meter.power_l2, meter.power_l3)
    known = [power for power in powers if power is not None]
    return sum(known) if len(known) == len(powers) else None


POWER_METER_SENSORS: tuple[E3dcPartSensorDescription, ...] = (
    E3dcPartSensorDescription(
        key="type",
        translation_key="power_meter_type",
        device_class=SensorDeviceClass.ENUM,
        options=_enum_options(PowerMeterType),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device, number: device.power_meter_readings[number].meter_type,
    ),
    E3dcPartSensorDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device, number: _total(device.power_meter_readings[number]),
    ),
    *(
        E3dcPartSensorDescription(
            key=f"power_{phase}",
            translation_key="power_phase",
            translation_placeholders={"phase": phase.upper()},
            device_class=SensorDeviceClass.POWER,
            native_unit_of_measurement=UnitOfPower.WATT,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
            value_fn=_meter_phase_power(phase),
        )
        for phase in PHASES
    ),
)


def _inverter(device: E3dcPowerStation, number: int) -> Inverter:
    """Inverter slot ``number``, which only exists when the slot answered."""
    if TYPE_CHECKING:
        assert device.inverters is not None
    return device.inverters[number]


@dataclass(frozen=True, kw_only=True)
class _InverterQuantity:
    """A quantity an inverter reports, e.g. once per phase."""

    device_class: SensorDeviceClass
    unit: str
    suggested_display_precision: int | None = None
    enabled_default: bool = False


PHASE_QUANTITIES = {
    "active_power": _InverterQuantity(
        device_class=SensorDeviceClass.POWER,
        unit=UnitOfPower.WATT,
        enabled_default=True,
    ),
    "apparent_power": _InverterQuantity(
        device_class=SensorDeviceClass.APPARENT_POWER,
        unit=UnitOfApparentPower.VOLT_AMPERE,
    ),
    "reactive_power": _InverterQuantity(
        device_class=SensorDeviceClass.REACTIVE_POWER,
        unit=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
    ),
    "voltage": _InverterQuantity(
        device_class=SensorDeviceClass.VOLTAGE,
        unit=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
    ),
    "current": _InverterQuantity(
        device_class=SensorDeviceClass.CURRENT,
        unit=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
    ),
}
DC_QUANTITIES = {
    "dc_power": _InverterQuantity(
        device_class=SensorDeviceClass.POWER,
        unit=UnitOfPower.WATT,
        enabled_default=True,
    ),
    "dc_voltage": _InverterQuantity(
        device_class=SensorDeviceClass.VOLTAGE,
        unit=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
    ),
    "dc_current": _InverterQuantity(
        device_class=SensorDeviceClass.CURRENT,
        unit=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
    ),
}


def _inverter_sensor(
    key: str,
    quantity: _InverterQuantity,
    translation_key: str | None = None,
    translation_placeholders: Mapping[str, str] | None = None,
) -> E3dcPartSensorDescription:
    """A sensor for the inverter attribute named ``key``."""
    get = attrgetter(key)
    return E3dcPartSensorDescription(
        key=key,
        translation_key=translation_key,
        translation_placeholders=translation_placeholders,
        device_class=quantity.device_class,
        native_unit_of_measurement=quantity.unit,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=quantity.suggested_display_precision,
        entity_registry_enabled_default=quantity.enabled_default,
        value_fn=lambda device, number: get(_inverter(device, number)),
    )


INVERTER_SENSORS: tuple[E3dcPartSensorDescription, ...] = (
    *(
        _inverter_sensor(
            f"{name}_{phase}",
            quantity,
            f"{name}_phase",
            {"phase": phase.upper()},
        )
        for name, quantity in PHASE_QUANTITIES.items()
        for phase in PHASES
    ),
    _inverter_sensor(
        "frequency",
        _InverterQuantity(
            device_class=SensorDeviceClass.FREQUENCY,
            unit=UnitOfFrequency.HERTZ,
            suggested_display_precision=2,
        ),
    ),
    *(
        _inverter_sensor(f"{name}_{tracker}", quantity, name, {"tracker": str(tracker)})
        for name, quantity in DC_QUANTITIES.items()
        for tracker in DC_TRACKERS
    ),
)


def _installed_meters(device: E3dcPowerStation) -> list[int]:
    """The power meter slots with a meter configured, other than the grid connection point.

    The power station's own sensors cover the meter at the grid connection point.
    """
    return [
        number
        for number, meter in device.power_meter_readings.items()
        if meter.is_installed and meter.meter_type is not PowerMeterType.ROOT
    ]


def _connected_inverters(device: E3dcPowerStation) -> list[int]:
    """The power station's own inverter, and each additional one on the grid."""
    return [
        number
        for number, inverter in (device.inverters or {}).items()
        if number == 0 or inverter.is_connected
    ]


@dataclass(frozen=True, kw_only=True)
class _PartKind:
    """A kind of part that gets a device for each slot the power station reports."""

    kind: PartKind
    present_fn: Callable[[E3dcPowerStation], Iterable[int]]
    sensors: tuple[E3dcPartSensorDescription, ...]


PARTS = (
    _PartKind(
        kind=PartKind.POWER_METER,
        present_fn=_installed_meters,
        sensors=POWER_METER_SENSORS,
    ),
    _PartKind(
        kind=PartKind.INVERTER,
        present_fn=_connected_inverters,
        sensors=INVERTER_SENSORS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: E3dcConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the E3/DC sensor platform."""
    coordinator = entry.runtime_data
    device = coordinator.device
    served = {*device.readings_components, *device.settings_components}
    # The keys of the station sensors that are already added
    added_sensors: set[str] = set()
    # The parts whose sensors are already added, by kind and slot
    added_parts: set[tuple[PartKind, int]] = set()

    @callback
    def _async_add_new() -> None:
        """Add sensors for hardware the first time the power station reports it."""
        entities: list[SensorEntity] = []
        for description in SENSORS:
            if (
                description.key not in added_sensors
                and description.component in served
                and description.exists_fn(device)
            ):
                added_sensors.add(description.key)
                entities.append(E3dcSensor(coordinator, description))
        for part_kind in PARTS:
            for slot in part_kind.present_fn(device):
                if (part_kind.kind, slot) in added_parts:
                    continue
                added_parts.add((part_kind.kind, slot))
                part = E3dcPart(kind=part_kind.kind, slot=slot)
                entities.extend(
                    E3dcPartSensor(coordinator, description, part, part_kind)
                    for description in part_kind.sensors
                )
        if entities:
            async_add_entities(entities)

    _async_add_new()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new))


def _state(value: StateType | IntEnum) -> StateType:
    """The sensor state for a value, with enum members as their option."""
    if isinstance(value, IntEnum):
        return value.name.lower()
    return value


class E3dcSensor(E3dcEntity, SensorEntity):
    """Defines an E3/DC sensor."""

    entity_description: E3dcSensorDescription

    @property
    @override
    def available(self) -> bool:
        return super().available and self.entity_description.exists_fn(
            self.coordinator.device
        )

    @property
    @override
    def native_value(self) -> StateType:
        return _state(self.entity_description.value_fn(self.coordinator.device))


class E3dcPartSensor(E3dcEntity, SensorEntity):
    """Defines a sensor of a power meter or an inverter."""

    entity_description: E3dcPartSensorDescription

    def __init__(
        self,
        coordinator: E3dcDataUpdateCoordinator,
        entity_description: E3dcPartSensorDescription,
        part: E3dcPart,
        part_kind: _PartKind,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entity_description, part)
        self._slot = part.slot
        self._present_fn = part_kind.present_fn

    @property
    @override
    def available(self) -> bool:
        return super().available and self._slot in self._present_fn(
            self.coordinator.device
        )

    @property
    @override
    def native_value(self) -> StateType:
        return _state(
            self.entity_description.value_fn(self.coordinator.device, self._slot)
        )
