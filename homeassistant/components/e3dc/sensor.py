"""Support for E3/DC sensors."""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
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
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import ChildDeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import E3dcConfigEntry, E3dcDataUpdateCoordinator
from .entity import E3dcEntity, E3dcPart, part_device_info

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


def _meter_phase_powers(
    device: E3dcPowerStation, number: int
) -> tuple[int | None, int | None, int | None]:
    """The phase powers of power meter slot ``number``."""
    meter = device.power_meter_readings[number]
    return meter.power_l1, meter.power_l2, meter.power_l3


def _meter_phase_power(phase: str) -> Callable[[E3dcPowerStation, int], StateType]:
    """Read the power on ``phase`` of a power meter slot."""
    get = attrgetter(f"power_{phase}")
    return lambda device, number: get(device.power_meter_readings[number])


def _total(values: Iterable[int | None]) -> int | None:
    """The sum of the phase values, or ``None`` if any is unknown."""
    values = tuple(values)
    known = [value for value in values if value is not None]
    return sum(known) if len(known) == len(values) else None


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
        value_fn=lambda device, number: _total(_meter_phase_powers(device, number)),
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


def _inverter_sensor(
    key: str,
    device_class: SensorDeviceClass,
    unit: str,
    *,
    translation_key: str | None = None,
    translation_placeholders: Mapping[str, str] | None = None,
    suggested_display_precision: int | None = None,
    enabled_default: bool = False,
) -> E3dcPartSensorDescription:
    """A sensor for the inverter attribute named ``key``."""
    get = attrgetter(key)
    return E3dcPartSensorDescription(
        key=key,
        translation_key=translation_key,
        translation_placeholders=translation_placeholders,
        device_class=device_class,
        native_unit_of_measurement=unit,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=suggested_display_precision,
        entity_registry_enabled_default=enabled_default,
        value_fn=lambda device, number: get(_inverter(device, number)),
    )


INVERTER_SENSORS: tuple[E3dcPartSensorDescription, ...] = (
    *(
        _inverter_sensor(
            f"active_power_{phase}",
            SensorDeviceClass.POWER,
            UnitOfPower.WATT,
            translation_key="active_power_phase",
            translation_placeholders={"phase": phase.upper()},
            enabled_default=True,
        )
        for phase in PHASES
    ),
    *(
        _inverter_sensor(
            f"apparent_power_{phase}",
            SensorDeviceClass.APPARENT_POWER,
            UnitOfApparentPower.VOLT_AMPERE,
            translation_key="apparent_power_phase",
            translation_placeholders={"phase": phase.upper()},
        )
        for phase in PHASES
    ),
    *(
        _inverter_sensor(
            f"reactive_power_{phase}",
            SensorDeviceClass.REACTIVE_POWER,
            UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
            translation_key="reactive_power_phase",
            translation_placeholders={"phase": phase.upper()},
        )
        for phase in PHASES
    ),
    *(
        _inverter_sensor(
            f"voltage_{phase}",
            SensorDeviceClass.VOLTAGE,
            UnitOfElectricPotential.VOLT,
            translation_key="voltage_phase",
            translation_placeholders={"phase": phase.upper()},
            suggested_display_precision=1,
        )
        for phase in PHASES
    ),
    *(
        _inverter_sensor(
            f"current_{phase}",
            SensorDeviceClass.CURRENT,
            UnitOfElectricCurrent.AMPERE,
            translation_key="current_phase",
            translation_placeholders={"phase": phase.upper()},
            suggested_display_precision=2,
        )
        for phase in PHASES
    ),
    _inverter_sensor(
        "frequency",
        SensorDeviceClass.FREQUENCY,
        UnitOfFrequency.HERTZ,
        suggested_display_precision=2,
    ),
    *(
        _inverter_sensor(
            f"dc_power_{tracker}",
            SensorDeviceClass.POWER,
            UnitOfPower.WATT,
            translation_key="dc_power",
            translation_placeholders={"tracker": str(tracker)},
            enabled_default=True,
        )
        for tracker in DC_TRACKERS
    ),
    *(
        _inverter_sensor(
            f"dc_voltage_{tracker}",
            SensorDeviceClass.VOLTAGE,
            UnitOfElectricPotential.VOLT,
            translation_key="dc_voltage",
            translation_placeholders={"tracker": str(tracker)},
            suggested_display_precision=1,
        )
        for tracker in DC_TRACKERS
    ),
    *(
        _inverter_sensor(
            f"dc_current_{tracker}",
            SensorDeviceClass.CURRENT,
            UnitOfElectricCurrent.AMPERE,
            translation_key="dc_current",
            translation_placeholders={"tracker": str(tracker)},
            suggested_display_precision=2,
        )
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

    kind: str
    present_fn: Callable[[E3dcPowerStation], Iterable[int]]
    sensors: tuple[E3dcPartSensorDescription, ...]


PARTS = (
    _PartKind(
        kind="power_meter", present_fn=_installed_meters, sensors=POWER_METER_SENSORS
    ),
    _PartKind(
        kind="inverter", present_fn=_connected_inverters, sensors=INVERTER_SENSORS
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
    device_registry = dr.async_get(hass)
    added_sensors: set[str] = set()
    added_parts: dict[tuple[str, int], E3dcPart] = {}

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
            slots = list(part_kind.present_fn(device))
            known = {slot for kind, slot in added_parts if kind == part_kind.kind}
            # Number the parts once the power station has had several of a kind
            numbered = len({*slots, *known}) > 1
            for slot in slots:
                if (part_kind.kind, slot) in added_parts:
                    continue
                part = E3dcPart(kind=part_kind.kind, slot=slot, numbered=numbered)
                added_parts[part_kind.kind, slot] = part
                entities.extend(
                    E3dcPartSensor(coordinator, description, part)
                    for description in part_kind.sensors
                )
            if numbered:
                _async_number_parts(part_kind.kind)
        if entities:
            async_add_entities(entities)

    @callback
    def _async_number_parts(kind: str) -> None:
        """Rename the devices of the parts added while they were the only one."""
        for key, part in added_parts.items():
            if part.kind != kind or part.numbered:
                continue
            part = added_parts[key] = replace(part, numbered=True)
            device_info = part_device_info(coordinator, part)
            if isinstance(device_info, ChildDeviceInfo):
                device_registry.async_get_or_create_child_from_info(
                    config_entry_id=entry.entry_id, device_info=device_info
                )
            else:
                device_registry.async_get_or_create_from_info(
                    config_entry_id=entry.entry_id, device_info=device_info
                )

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
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entity_description, part)
        self._slot = part.slot

    @property
    @override
    def native_value(self) -> StateType:
        return _state(
            self.entity_description.value_fn(self.coordinator.device, self._slot)
        )
