"""Sensor platform for the Silla Prism integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from pysillaprism import PortState, PrismStatus

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
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import PORT
from .coordinator import PrismConfigEntry, PrismCoordinator
from .entity import PrismEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PrismSensorEntityDescription(SensorEntityDescription):
    """Describes a Prism sensor."""

    value_fn: Callable[[PrismStatus], StateType]


def _port_state(status: PrismStatus) -> str | None:
    state = status.port(PORT).state
    return state.name.lower() if state is not None else None


SENSORS: tuple[PrismSensorEntityDescription, ...] = (
    PrismSensorEntityDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=[state.name.lower() for state in PortState],
        value_fn=_port_state,
    ),
    PrismSensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.port(PORT).power,
    ),
    PrismSensorEntityDescription(
        key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        # Prism reports the delivered current in milliamps.
        value_fn=lambda status: (
            None if (amp := status.port(PORT).current) is None else amp / 1000
        ),
    ),
    PrismSensorEntityDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: status.port(PORT).voltage,
    ),
    PrismSensorEntityDescription(
        key="pilot",
        translation_key="pilot",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: status.port(PORT).pilot,
    ),
    PrismSensorEntityDescription(
        key="session_energy",
        translation_key="session_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda status: status.port(PORT).session_energy,
    ),
    PrismSensorEntityDescription(
        key="total_energy",
        translation_key="total_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda status: status.port(PORT).total_energy,
    ),
    PrismSensorEntityDescription(
        key="session_time",
        translation_key="session_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: status.port(PORT).session_time,
    ),
    PrismSensorEntityDescription(
        key="error",
        translation_key="error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: status.port(PORT).error,
    ),
    PrismSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: status.temperature,
    ),
    PrismSensorEntityDescription(
        key="grid_power",
        translation_key="grid_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.energy.power_grid,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PrismConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Prism sensors."""
    coordinator = entry.runtime_data
    async_add_entities(PrismSensor(coordinator, description) for description in SENSORS)


class PrismSensor(PrismEntity, SensorEntity):
    """A Prism sensor backed by an accumulated status field."""

    entity_description: PrismSensorEntityDescription

    def __init__(
        self,
        coordinator: PrismCoordinator,
        description: PrismSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> StateType:
        """Return the current value from the accumulated status."""
        return self.entity_description.value_fn(self.coordinator.device.status)
