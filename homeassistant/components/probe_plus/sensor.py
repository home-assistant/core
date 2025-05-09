"""Support for Probe Plus BLE sensors."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant import config_entries
from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ProbePlusDevice
from .entity import ProbePlusEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class ProbePlusSensorEntityDescription(SensorEntityDescription):
    """Description for Probe Plus sensor entities."""

    value_fn: Callable[[ProbePlusDevice], int | float | None]


SENSOR_DESCRIPTIONS: tuple[ProbePlusSensorEntityDescription, ...] = (
    ProbePlusSensorEntityDescription(
        key="probe_temperature",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda device: device.device_state.probe_temperature,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    ProbePlusSensorEntityDescription(
        key="probe_battery",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda device: device.device_state.probe_battery,
        device_class=SensorDeviceClass.BATTERY,
    ),
    ProbePlusSensorEntityDescription(
        key="relay_battery",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda device: device.device_state.relay_battery,
        device_class=SensorDeviceClass.BATTERY,
    ),
    ProbePlusSensorEntityDescription(
        key="probe_rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.device_state.probe_rssi,
        entity_registry_enabled_default=False
    ),
    ProbePlusSensorEntityDescription(
        key="relay_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.VOLTAGE,
        value_fn=lambda device: device.device_state.relay_voltage,
        entity_registry_enabled_default=False,
    ),
    ProbePlusSensorEntityDescription(
        key="probe_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.VOLTAGE,
        value_fn=lambda device: device.device_state.probe_voltage,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Probe Plus sensors."""
    coordinator = entry.runtime_data
    async_add_entities([
        ProbeSensor(coordinator=coordinator, entity_description=desc)
        for desc in SENSOR_DESCRIPTIONS
    ])


class ProbeSensor(ProbePlusEntity, RestoreSensor):
    """Representation of a Probe Plus sensor."""

    entity_description: ProbePlusSensorEntityDescription

    @property
    def native_value(self) -> int | float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.device)
