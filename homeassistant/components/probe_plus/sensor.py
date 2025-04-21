"""Support for Probe Plus BLE sensors."""

from collections.abc import Callable
from dataclasses import dataclass
import logging

from homeassistant import config_entries
from homeassistant.components.sensor import (
    RestoreSensor,
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

from .coordinator import ProbePlusDataUpdateCoordinator, ProbePlusDevice
from .entity import ProbePlusEntity

_LOGGER = logging.getLogger(__name__)

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class ProbePlusSensorEntityDescription(SensorEntityDescription):
    """Description for Probe Plus sensor entities."""

    value_fn: Callable[[ProbePlusDevice], int | float | None]


SENSOR_DESCRIPTIONS: tuple[ProbePlusSensorEntityDescription, ...] = (
    ProbePlusSensorEntityDescription(
        key="probe_temperature",
        icon="mdi:thermometer-bluetooth",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda device: device.device_state.probe_temperature,
        name="Probe Temperature",
    ),
    ProbePlusSensorEntityDescription(
        key="probe_battery",
        icon="mdi:battery",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda device: device.device_state.probe_battery,
        name="Probe Battery",
    ),
    ProbePlusSensorEntityDescription(
        key="relay_battery",
        icon="mdi:battery",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda device: device.device_state.relay_battery,
        name="Relay Battery",
    ),
    ProbePlusSensorEntityDescription(
        key="probe_rssi",
        icon="mdi:bluetooth-connect",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.device_state.probe_rssi,
        name="Probe Signal Strength",
    ),
    ProbePlusSensorEntityDescription(
        key="relay_voltage",
        icon="mdi:flash-triangle",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.device_state.relay_voltage,
        name="Relay Voltage",
    ),
    ProbePlusSensorEntityDescription(
        key="probe_voltage",
        icon="mdi:flash-triangle",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.device_state.probe_voltage,
        name="Probe Voltage",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Probe Plus sensors."""
    _LOGGER.debug("Setting up Probe Plus sensors for entry: %s", entry.entry_id)
    coordinator: ProbePlusDataUpdateCoordinator = entry.runtime_data
    entities = [
        ProbeSensor(coordinator=coordinator, entity_description=desc)
        for desc in SENSOR_DESCRIPTIONS
    ]
    async_add_entities(entities)
    _LOGGER.debug("Probe sensors setup completed for entry: %s", entry.entry_id)


class ProbeSensor(ProbePlusEntity, RestoreSensor):
    """Representation of a Probe Plus sensor."""

    entity_description: ProbePlusSensorEntityDescription

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of this entity."""
        return self.entity_description.native_unit_of_measurement

    @property
    def native_value(self) -> int | float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.device)
