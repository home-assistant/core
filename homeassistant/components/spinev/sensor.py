"""Sensors for the Spin EV Charger integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from spinev_ble import ChargerState, ChargerStatus

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

from .coordinator import SpinEvConfigEntry
from .entity import SpinEvEntity

PARALLEL_UPDATES = 0

STATE_OPTIONS = [state.name.lower() for state in ChargerState]


@dataclass(frozen=True, kw_only=True)
class SpinEvSensorEntityDescription(SensorEntityDescription):
    """Describes a Spin EV sensor."""

    value_fn: Callable[[ChargerStatus], StateType]


SENSORS: tuple[SpinEvSensorEntityDescription, ...] = (
    SpinEvSensorEntityDescription(
        key="state",
        translation_key="state",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_OPTIONS,
        value_fn=lambda status: status.state.name.lower() if status.state else None,
    ),
    SpinEvSensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda status: status.power_w,
    ),
    SpinEvSensorEntityDescription(
        key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda status: status.current_a,
    ),
    SpinEvSensorEntityDescription(
        key="session_energy",
        translation_key="session_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda status: status.session_energy_kwh,
    ),
    SpinEvSensorEntityDescription(
        key="lifetime_energy",
        translation_key="lifetime_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda status: status.lifetime_energy_kwh,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SpinEvConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the charger sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        SpinEvSensor(coordinator, description) for description in SENSORS
    )


class SpinEvSensor(SpinEvEntity, SensorEntity):
    """A value read from the charger."""

    entity_description: SpinEvSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the value reported by the charger."""
        return self.entity_description.value_fn(self.coordinator.data)
