"""Support for Voltie charger sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from voltie import EvseState

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfElectricCurrent, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import VoltieChargerConfigEntry, VoltieChargerData
from .entity import VoltieChargerEntity

PARALLEL_UPDATES = 0

EVSE_STATE_OPTIONS = [
    state.name.lower() for state in EvseState if state is not EvseState.UNKNOWN
]


@dataclass(frozen=True, kw_only=True)
class VoltieSensorEntityDescription(SensorEntityDescription):
    """Describes a sensor of the live data."""

    exists_fn: Callable[[VoltieChargerData], bool] = lambda _: True
    value_fn: Callable[[VoltieChargerData], StateType]


def _evse_state(data: VoltieChargerData) -> str | None:
    """Return the EVSE state, unknown before its first reading."""
    state = data.status.evse_state
    if state is None or state is EvseState.UNKNOWN:
        return None
    return state.name.lower()


def _session_energy(data: VoltieChargerData) -> float | None:
    """Return the energy of the active session.

    An idle charger reads 0 rather than unknown: weeks of unknown would let
    the recorder drop the last statistics of this counter, after which it
    counts the next session from scratch.
    """
    status = data.status
    if status.session is not None:
        return status.session.energy
    if status.session_known and status.evse_state is EvseState.EV_NOT_CONNECTED:
        return 0
    return None


DESCRIPTIONS: tuple[VoltieSensorEntityDescription, ...] = (
    VoltieSensorEntityDescription(
        key="evse_state",
        translation_key="evse_state",
        device_class=SensorDeviceClass.ENUM,
        options=EVSE_STATE_OPTIONS,
        value_fn=_evse_state,
    ),
    VoltieSensorEntityDescription(
        key="charge_power",
        translation_key="charge_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: data.status.charge_power,
    ),
    VoltieSensorEntityDescription(
        key="charge_current",
        translation_key="charge_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.status.charge_current,
    ),
    VoltieSensorEntityDescription(
        key="session_energy",
        translation_key="session_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=_session_energy,
    ),
    VoltieSensorEntityDescription(
        key="total_energy",
        translation_key="total_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        exists_fn=lambda data: data.status.meter_supported,
        value_fn=lambda data: data.status.meter_energy,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VoltieChargerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Voltie charger sensors based on a config entry."""
    runtime_data = entry.runtime_data
    entities: list[SensorEntity] = [
        VoltieSensorEntity(entry, runtime_data.data_coordinator, description)
        for description in DESCRIPTIONS
        if description.exists_fn(runtime_data.data_coordinator.data)
    ]
    async_add_entities(entities)


class VoltieSensorEntity(VoltieChargerEntity, SensorEntity):
    """Defines a sensor of the live data."""

    entity_description: VoltieSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
