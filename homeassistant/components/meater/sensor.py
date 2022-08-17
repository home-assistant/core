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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import dt as dt_util

from .const import DOMAIN


@dataclass
class MeaterSensorEntityDescriptionMixin:
    """Mixin for MeaterSensorEntityDescription."""

    available: Callable[[MeaterProbe | None], bool]
    value: Callable[[MeaterProbe], datetime | float | str | None]


@dataclass
class MeaterSensorEntityDescription(
    SensorEntityDescription, MeaterSensorEntityDescriptionMixin
):
    """Describes meater sensor entity."""


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
        device_class=SensorDeviceClass.TEMPERATURE,
        name="Ambient",
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        available=lambda probe: probe is not None,
        value=lambda probe: probe.ambient_temperature,
    ),
    # Internal temperature (probe tip)
    MeaterSensorEntityDescription(
        key="internal",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="Internal",
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        available=lambda probe: probe is not None,
        value=lambda probe: probe.internal_temperature,
    ),
    # Name of selected meat in user language or user given custom name
    MeaterSensorEntityDescription(
        key="cook_name",
        name="Cooking",
        available=lambda probe: probe is not None and probe.cook is not None,
        value=lambda probe: probe.cook.name if probe.cook else None,
    ),
    # One of Not Started, Configured, Started, Ready For Resting, Resting,
    # Slightly Underdone, Finished, Slightly Overdone, OVERCOOK!. Not translated.
    MeaterSensorEntityDescription(
        key="cook_state",
        name="Cook state",
        available=lambda probe: probe is not None and probe.cook is not None,
        value=lambda probe: probe.cook.state if probe.cook else None,
    ),
    # Target temperature
    MeaterSensorEntityDescription(
        key="cook_target_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="Target",
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        available=lambda probe: probe is not None and probe.cook is not None,
        value=lambda probe: probe.cook.target_temperature
        if probe.cook and hasattr(probe.cook, "target_temperature")
        else None,
    ),
    # Peak temperature
    MeaterSensorEntityDescription(
        key="cook_peak_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="Peak",
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        available=lambda probe: probe is not None and probe.cook is not None,
        value=lambda probe: probe.cook.peak_temperature
        if probe.cook and hasattr(probe.cook, "peak_temperature")
        else None,
    ),
    # Remaining time in seconds. When unknown/calculating default is used. Default: -1
    # Exposed as a TIMESTAMP sensor where the timestamp is current time + remaining time.
    MeaterSensorEntityDescription(
        key="cook_time_remaining",
        device_class=SensorDeviceClass.TIMESTAMP,
        name="Remaining time",
        available=lambda probe: probe is not None and probe.cook is not None,
        value=_remaining_time_to_timestamp,
    ),
    # Time since the start of cook in seconds. Default: 0. Exposed as a TIMESTAMP sensor
    # where the timestamp is current time - elapsed time.
    MeaterSensorEntityDescription(
        key="cook_time_elapsed",
        device_class=SensorDeviceClass.TIMESTAMP,
        name="Elapsed time",
        available=lambda probe: probe is not None and probe.cook is not None,
        value=_elapsed_time_to_timestamp,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the entry."""
    coordinator: DataUpdateCoordinator[dict[str, MeaterProbe]] = hass.data[DOMAIN][
        entry.entry_id
    ]["coordinator"]

    @callback
    def async_update_data():
        """Handle updated data from the API endpoint."""
        if not coordinator.last_update_success:
            return

        devices = coordinator.data
        entities = []
        known_probes: set = hass.data[DOMAIN]["known_probes"]

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


class MeaterProbeTemperature(
    SensorEntity, CoordinatorEntity[DataUpdateCoordinator[dict[str, MeaterProbe]]]
):
    """Meater Temperature Sensor Entity."""

    entity_description: MeaterSensorEntityDescription

    def __init__(
        self, coordinator, device_id, description: MeaterSensorEntityDescription
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._attr_name = f"Meater Probe {description.name}"
        self._attr_device_info = {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, device_id)
            },
            "manufacturer": "Apption Labs",
            "model": "Meater Probe",
            "name": f"Meater Probe {device_id}",
        }
        self._attr_unique_id = f"{device_id}-{description.key}"

        self.device_id = device_id
        self.entity_description = description

    @property
    def native_value(self):
        """Return the temperature of the probe."""
        if not (device := self.coordinator.data.get(self.device_id)):
            return None

        return self.entity_description.value(device)

    @property
    def available(self):
        """Return if entity is available."""
        # See if the device was returned from the API. If not, it's offline
        return (
            self.coordinator.last_update_success
            and self.entity_description.available(
                self.coordinator.data.get(self.device_id)
            )
        )
