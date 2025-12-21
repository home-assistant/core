"""The Meater Temperature Probe integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from meater.MeaterApi import MeaterProbe

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import MeaterCoordinator
from .const import DOMAIN, MEATER_DATA
from .coordinator import MeaterConfigEntry

COOK_STATES = {
    "Not Started": "not_started",
    "Configured": "configured",
    "Started": "started",
    "Ready For Resting": "ready_for_resting",
    "Resting": "resting",
    "Slightly Underdone": "slightly_underdone",
    "Finished": "finished",
    "Slightly Overdone": "slightly_overdone",
    "OVERCOOK!": "overcooked",
}


@dataclass(frozen=True, kw_only=True)
class MeaterSensorEntityDescription(SensorEntityDescription):
    """Describes meater sensor entity."""

    value: Callable[[MeaterProbe], datetime | float | str | None]
    unavailable_when_not_cooking: bool = False


def _elapsed_time_to_timestamp(probe: MeaterProbe) -> datetime | None:
    """Convert elapsed time to timestamp."""
    if not probe.cook or not hasattr(probe.cook, "time_elapsed"):
        return None
    return dt_util.utcnow() - timedelta(seconds=probe.cook.time_elapsed)


def _remaining_time_to_timestamp(probe: MeaterProbe) -> datetime | None:
    """Convert remaining time to timestamp."""
    if (
        not probe.cook
        or not hasattr(probe.cook, "time_remaining")
        or probe.cook.time_remaining < 0
    ):
        return None
    return dt_util.utcnow() + timedelta(seconds=probe.cook.time_remaining)


SENSOR_TYPES = (
    # Ambient temperature
    MeaterSensorEntityDescription(
        key="ambient",
        translation_key="ambient",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda probe: probe.ambient_temperature,
    ),
    # Internal temperature (probe tip)
    MeaterSensorEntityDescription(
        key="internal",
        translation_key="internal",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda probe: probe.internal_temperature,
    ),
    # Name of selected meat in user language or user given custom name
    MeaterSensorEntityDescription(
        key="cook_name",
        translation_key="cook_name",
        unavailable_when_not_cooking=True,
        value=lambda probe: probe.cook.name if probe.cook else None,
    ),
    MeaterSensorEntityDescription(
        key="cook_state",
        translation_key="cook_state",
        unavailable_when_not_cooking=True,
        device_class=SensorDeviceClass.ENUM,
        options=list(COOK_STATES.values()),
        value=lambda probe: COOK_STATES.get(probe.cook.state) if probe.cook else None,
    ),
    # Target temperature
    MeaterSensorEntityDescription(
        key="cook_target_temp",
        translation_key="cook_target_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        unavailable_when_not_cooking=True,
        value=(
            lambda probe: probe.cook.target_temperature
            if probe.cook and hasattr(probe.cook, "target_temperature")
            else None
        ),
    ),
    # Peak temperature
    MeaterSensorEntityDescription(
        key="cook_peak_temp",
        translation_key="cook_peak_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        unavailable_when_not_cooking=True,
        value=(
            lambda probe: probe.cook.peak_temperature
            if probe.cook and hasattr(probe.cook, "peak_temperature")
            else None
        ),
    ),
    # Remaining time in seconds. When unknown/calculating default is used. Default: -1
    # Exposed as a TIMESTAMP sensor where the timestamp is current time + remaining time.
    MeaterSensorEntityDescription(
        key="cook_time_remaining",
        translation_key="cook_time_remaining",
        device_class=SensorDeviceClass.TIMESTAMP,
        unavailable_when_not_cooking=True,
        value=_remaining_time_to_timestamp,
    ),
    # Time since the start of cook in seconds. Default: 0. Exposed as a TIMESTAMP sensor
    # where the timestamp is current time - elapsed time.
    MeaterSensorEntityDescription(
        key="cook_time_elapsed",
        translation_key="cook_time_elapsed",
        device_class=SensorDeviceClass.TIMESTAMP,
        unavailable_when_not_cooking=True,
        value=_elapsed_time_to_timestamp,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeaterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the entry."""
    coordinator = entry.runtime_data

    @callback
    def async_update_data():
        """Handle updated data from the API endpoint."""
        if not coordinator.last_update_success:
            return None

        devices = coordinator.data
        entities = []
        known_probes = hass.data[MEATER_DATA]

        # Add entities for temperature probes which we've not yet seen
        for device_id in devices:
            if device_id in known_probes:
                continue

            entities.extend(
                [
                    MeaterProbeTemperature(coordinator, device_id, sensor_description)
                    for sensor_description in SENSOR_TYPES
                ]
            )
            known_probes.add(device_id)

        async_add_entities(entities)

        return devices

    # Add a subscriber to the coordinator to discover new temperature probes
    coordinator.async_add_listener(async_update_data)
    async_update_data()


class MeaterProbeTemperature(SensorEntity, CoordinatorEntity[MeaterCoordinator]):
    """Meater Temperature Sensor Entity."""

    _attr_has_entity_name = True
    entity_description: MeaterSensorEntityDescription

    def __init__(
        self,
        coordinator: MeaterCoordinator,
        device_id: str,
        description: MeaterSensorEntityDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, device_id)
            },
            manufacturer="Apption Labs",
            model="Meater Probe",
            name=f"Meater Probe {device_id[:8]}",
        )
        self._attr_unique_id = f"{device_id}-{description.key}"

        self.device_id = device_id
        self.entity_description = description

    @property
    def probe(self) -> MeaterProbe:
        """Return the probe."""
        return self.coordinator.data[self.device_id]

    @property
    def native_value(self) -> datetime | float | str | None:
        """Return the temperature of the probe."""
        return self.entity_description.value(self.probe)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # See if the device was returned from the API. If not, it's offline
        return (
            super().available
            and self.device_id in self.coordinator.data
            and (
                not self.entity_description.unavailable_when_not_cooking
                or self.probe.cook is not None
            )
        )
