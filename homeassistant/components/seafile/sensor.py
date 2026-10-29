"""Sensor platform for the Seafile integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import SUBENTRY_TYPE_LIBRARY
from .coordinator import SeafileConfigEntry, SeafileData, SeafileDataUpdateCoordinator
from .entity import SeafileEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SeafileSensorEntityDescription(SensorEntityDescription):
    """Describes a sensor of a Seafile library."""

    value_fn: Callable[[SeafileData, str], StateType | datetime]


SENSORS: tuple[SeafileSensorEntityDescription, ...] = (
    SeafileSensorEntityDescription(
        key="size",
        translation_key="size",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=2,
        value_fn=lambda data, library_id: data.libraries[library_id].size,
    ),
    SeafileSensorEntityDescription(
        key="file_count",
        translation_key="file_count",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data, library_id: data.file_counts.get(library_id),
    ),
    SeafileSensorEntityDescription(
        key="last_modified",
        translation_key="last_modified",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data, library_id: data.libraries[library_id].modified,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SeafileConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Seafile sensors."""
    coordinator = entry.runtime_data
    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_LIBRARY):
        async_add_entities(
            (
                SeafileSensor(coordinator, subentry, description)
                for description in SENSORS
            ),
            config_subentry_id=subentry.subentry_id,
        )


class SeafileSensor(SeafileEntity, SensorEntity):
    """Sensor of a Seafile library."""

    entity_description: SeafileSensorEntityDescription

    def __init__(
        self,
        coordinator: SeafileDataUpdateCoordinator,
        subentry: ConfigSubentry,
        description: SeafileSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, subentry, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data, self.library_id)
