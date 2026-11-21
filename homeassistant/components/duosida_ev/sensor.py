"""Sensor platform for the Duosida EV Charger integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from duosida_ev import ChargerState, ChargerStatus

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

from .coordinator import DuosidaConfigEntry, DuosidaCoordinator
from .entity import DuosidaEntity

PARALLEL_UPDATES = 0

# OCPP 1.6 connector states. "Unavailable" is renamed, as that is a reserved
# entity state in Home Assistant.
STATUS_OPTIONS: dict[ChargerState, str] = {
    ChargerState.AVAILABLE: "available",
    ChargerState.PREPARING: "preparing",
    ChargerState.CHARGING: "charging",
    ChargerState.SUSPENDED_EVSE: "suspended_evse",
    ChargerState.SUSPENDED_EV: "suspended_ev",
    ChargerState.FINISHING: "finishing",
    ChargerState.RESERVED: "reserved",
    ChargerState.UNAVAILABLE: "inoperative",
    ChargerState.FAULTED: "faulted",
}


@dataclass(frozen=True, kw_only=True)
class DuosidaSensorEntityDescription(SensorEntityDescription):
    """Describes a Duosida sensor entity."""

    value_fn: Callable[[ChargerStatus], StateType]


SENSORS: tuple[DuosidaSensorEntityDescription, ...] = (
    DuosidaSensorEntityDescription(
        key="state",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=list(STATUS_OPTIONS.values()),
        value_fn=lambda status: STATUS_OPTIONS.get(status.state),
    ),
    DuosidaSensorEntityDescription(
        key="voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.voltage,
    ),
    DuosidaSensorEntityDescription(
        key="current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.current,
    ),
    DuosidaSensorEntityDescription(
        key="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.power,
    ),
    DuosidaSensorEntityDescription(
        key="session_energy",
        translation_key="session_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda status: status.session_energy,
    ),
    DuosidaSensorEntityDescription(
        key="total_energy",
        translation_key="total_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda status: status.total_energy,
    ),
    DuosidaSensorEntityDescription(
        key="session_time",
        translation_key="session_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda status: (
            None
            if (duration := status.session_duration) is None
            else duration.total_seconds() / 60
        ),
    ),
    DuosidaSensorEntityDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: status.temperature,
    ),
    DuosidaSensorEntityDescription(
        key="cp_voltage",
        translation_key="cp_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.cp_voltage,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DuosidaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Duosida sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        DuosidaSensor(coordinator, description) for description in SENSORS
    )


class DuosidaSensor(DuosidaEntity, SensorEntity):
    """A sensor reading one value of the charger's status."""

    entity_description: DuosidaSensorEntityDescription

    def __init__(
        self,
        coordinator: DuosidaCoordinator,
        description: DuosidaSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
