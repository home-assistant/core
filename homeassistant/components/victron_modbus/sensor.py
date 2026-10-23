"""Sensor platform for Victron Modbus devices.

Every supported model (VM-3P75CT, VM-3P5A, P1Link) exposes the same shape:
``power`` (total and per phase), a ``meter`` with the grid totals, and three
``phase_N`` sub-systems with the same attribute names, so one set of sensor
descriptions covers all of them. A description only becomes an entity if the
device has that reading: its model must read the register (the P1Link has no
PE-N voltage or frequency), and the device must report a value for it. A
device reports a reading it lacks, such as a phase missing from a single-phase
connection, as unavailable, so such sensors are skipped at setup; sensors of
the phases the meter's configuration says aren't connected are skipped too.
"""

from dataclasses import dataclass, replace
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import VictronModbusConfigEntry
from .entity import VictronModbusEntity, VictronModbusEntityDescription

# Entities only ever read the coordinators' cached state between updates.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class VictronModbusSensorDescription(
    SensorEntityDescription, VictronModbusEntityDescription
):
    """Describe a Victron Modbus sensor."""


# The total power, read as ``power.total``.
_TOTAL_POWER = VictronModbusSensorDescription(
    key="total_power",
    translation_key="total_power",
    sub_system="power",
    device_class=SensorDeviceClass.POWER,
    native_unit_of_measurement=UnitOfPower.WATT,
    state_class=SensorStateClass.MEASUREMENT,
)

# Grid totals, read from ``meter`` under their own key.
_METER: tuple[VictronModbusSensorDescription, ...] = (
    VictronModbusSensorDescription(
        key="total_forward_energy",
        translation_key="total_forward_energy",
        sub_system="meter",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    VictronModbusSensorDescription(
        key="total_reverse_energy",
        translation_key="total_reverse_energy",
        sub_system="meter",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    VictronModbusSensorDescription(
        key="voltage_pen",
        translation_key="voltage_pen",
        sub_system="meter",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        # Near 0 V in a healthy installation; it shows earthing faults.
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)

# The grid frequency, read from ``meter.frequency_fine`` (0.001 Hz) where the
# meter's firmware has it, and from ``meter.frequency`` (0.01 Hz) otherwise.
_FREQUENCY = VictronModbusSensorDescription(
    key="frequency",
    sub_system="meter",
    device_class=SensorDeviceClass.FREQUENCY,
    native_unit_of_measurement=UnitOfFrequency.HERTZ,
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=2,
)
_FINE_FREQUENCY = replace(_FREQUENCY, suggested_display_precision=3)

# The power of each phase, read as ``power.l1`` to ``power.l3``.
_PHASE_POWER = VictronModbusSensorDescription(
    key="power",
    translation_key="phase_power",
    sub_system="power",
    device_class=SensorDeviceClass.POWER,
    native_unit_of_measurement=UnitOfPower.WATT,
    state_class=SensorStateClass.MEASUREMENT,
)

# The other per-phase readings, read from ``phase_N`` under their own key.
_PHASE: tuple[VictronModbusSensorDescription, ...] = (
    VictronModbusSensorDescription(
        key="voltage",
        translation_key="phase_voltage",
        sub_system="phases",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    VictronModbusSensorDescription(
        key="current",
        translation_key="phase_current",
        sub_system="phases",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    VictronModbusSensorDescription(
        key="forward_energy",
        translation_key="phase_forward_energy",
        sub_system="phases",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    VictronModbusSensorDescription(
        key="reverse_energy",
        translation_key="phase_reverse_energy",
        sub_system="phases",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VictronModbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Victron Modbus sensors."""
    data = entry.runtime_data
    device = data.power.device
    entities: list[VictronModbusSensor] = []

    def add(
        description: VictronModbusSensorDescription,
        component: str,
        attribute: str,
        phase: int | None = None,
    ) -> None:
        library_component = getattr(device, component)
        if attribute not in library_component.declared_fields:
            return
        # A reading the device reported as unavailable at setup is one it lacks.
        # A sub-system that failed to read says nothing, so keep its sensors.
        coordinator = data.coordinator_for(description.sub_system)
        if (
            description.sub_system in coordinator.data.updated
            and getattr(library_component, attribute) is None
        ):
            return
        entities.append(
            VictronModbusSensor(data, description, component, attribute, phase)
        )

    add(_TOTAL_POWER, "power", "total")
    for description in _METER:
        add(description, "meter", description.key)
    # The library drops the fine frequency from the fields it reads if its setup
    # probe finds the meter lacking it, so this doesn't depend on a poll's outcome.
    if "frequency_fine" in device.meter.resolved_fields:
        add(_FINE_FREQUENCY, "meter", "frequency_fine")
    else:
        add(_FREQUENCY, "meter", "frequency")
    # Only the phases the meter is connected to; the others report no readings.
    for phase in device.connected_phases:
        add(_PHASE_POWER, "power", f"l{phase}", phase)
        for description in _PHASE:
            add(description, f"phase_{phase}", description.key, phase)
    async_add_entities(entities)


class VictronModbusSensor(VictronModbusEntity, SensorEntity):
    """A single value read from a component attribute."""

    entity_description: VictronModbusSensorDescription

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current value."""
        return self._value
