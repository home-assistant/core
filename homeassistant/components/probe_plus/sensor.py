"""Support for Probe Plus BLE sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import override

from pyprobeplus.parsers.base import ProbeReading

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

from .coordinator import ProbePlusConfigEntry, ProbePlusDevice
from .entity import ProbePlusEntity, ProbePlusProbeEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


class ProbePlusSensor(StrEnum):
    """Store keys for Probe Plus sensors."""

    RELAY_BATTERY = "relay_battery"
    RELAY_VOLTAGE = "relay_voltage"
    PROBE_TEMPERATURE = "probe_temperature"
    PROBE_BATTERY = "probe_battery"
    PROBE_RSSI = "probe_rssi"
    PROBE_VOLTAGE = "probe_voltage"


@dataclass(kw_only=True, frozen=True)
class ProbePlusRelaySensorEntityDescription(SensorEntityDescription):
    """Description for Probe Plus relay sensor entities."""

    value_fn: Callable[[ProbePlusDevice], int | float | None]


@dataclass(kw_only=True, frozen=True)
class ProbePlusProbeSensorEntityDescription(SensorEntityDescription):
    """Description for Probe Plus probe sensor entities."""

    value_fn: Callable[[ProbeReading], int | float | None]


RELAY_SENSOR_DESCRIPTIONS: tuple[ProbePlusRelaySensorEntityDescription, ...] = (
    ProbePlusRelaySensorEntityDescription(
        key=ProbePlusSensor.RELAY_BATTERY,
        translation_key=ProbePlusSensor.RELAY_BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda device: device.device_state.relay_battery,
        device_class=SensorDeviceClass.BATTERY,
    ),
    ProbePlusRelaySensorEntityDescription(
        key=ProbePlusSensor.RELAY_VOLTAGE,
        translation_key=ProbePlusSensor.RELAY_VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.VOLTAGE,
        value_fn=lambda device: device.device_state.relay_voltage,
        entity_registry_enabled_default=False,
    ),
)
PROBE_SENSOR_DESCRIPTIONS: tuple[ProbePlusProbeSensorEntityDescription, ...] = (
    ProbePlusProbeSensorEntityDescription(
        key=ProbePlusSensor.PROBE_TEMPERATURE,
        translation_key=ProbePlusSensor.PROBE_TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda probe: probe.temperature,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    ProbePlusProbeSensorEntityDescription(
        key=ProbePlusSensor.PROBE_BATTERY,
        translation_key=ProbePlusSensor.PROBE_BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda probe: probe.battery,
        device_class=SensorDeviceClass.BATTERY,
    ),
    ProbePlusProbeSensorEntityDescription(
        key=ProbePlusSensor.PROBE_RSSI,
        translation_key=ProbePlusSensor.PROBE_RSSI,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda probe: probe.rssi,
        entity_registry_enabled_default=False,
    ),
    ProbePlusProbeSensorEntityDescription(
        key=ProbePlusSensor.PROBE_VOLTAGE,
        translation_key=ProbePlusSensor.PROBE_VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.VOLTAGE,
        value_fn=lambda probe: probe.voltage,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ProbePlusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Probe Plus sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        RelaySensor(coordinator, desc) for desc in RELAY_SENSOR_DESCRIPTIONS
    )

    coordinator.setup_dynamic_discovery(
        entry,
        async_add_entities,
        lambda slot: [
            ProbeSensor(coordinator, desc, slot) for desc in PROBE_SENSOR_DESCRIPTIONS
        ],
    )


class RelaySensor(ProbePlusEntity, RestoreSensor):
    """Representation of a Probe Plus sensor."""

    entity_description: ProbePlusRelaySensorEntityDescription

    @property
    @override
    def native_value(self) -> int | float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.device)


class ProbeSensor(ProbePlusProbeEntity, RestoreSensor):
    """Representation of a Probe Plus probe sensor."""

    entity_description: ProbePlusProbeSensorEntityDescription

    @property
    @override
    def native_value(self) -> int | float | None:
        """Return the state of the sensor."""
        if not self.probe:
            return None
        return self.entity_description.value_fn(self.probe)
