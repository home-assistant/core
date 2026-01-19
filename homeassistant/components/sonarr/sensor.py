"""Support for Sonarr sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic

from aiopyarr import (
    Command,
    Diskspace,
    SonarrCalendar,
    SonarrQueue,
    SonarrSeries,
    SonarrWantedMissing,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import SonarrConfigEntry, SonarrDataT, SonarrDataUpdateCoordinator
from .entity import SonarrEntity


@dataclass(frozen=True)
class SonarrSensorEntityDescriptionMixIn(Generic[SonarrDataT]):
    """Mixin for Sonarr sensor."""

    value_fn: Callable[[SonarrDataT], StateType]


@dataclass(frozen=True, kw_only=True)
class SonarrSensorEntityDescription(
    SensorEntityDescription, SonarrSensorEntityDescriptionMixIn[SonarrDataT]
):
    """Class to describe a Sonarr sensor."""


SENSOR_TYPES: dict[str, SonarrSensorEntityDescription[Any]] = {
    "commands": SonarrSensorEntityDescription[list[Command]](
        key="commands",
        translation_key="commands",
        entity_registry_enabled_default=False,
        value_fn=len,
    ),
    "diskspace": SonarrSensorEntityDescription[list[Diskspace]](
        key="diskspace",
        translation_key="diskspace",
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_registry_enabled_default=False,
        value_fn=lambda data: f"{sum(disk.freeSpace for disk in data) / 1024**3:.2f}",
    ),
    "queue": SonarrSensorEntityDescription[SonarrQueue](
        key="queue",
        translation_key="queue",
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.totalRecords,
    ),
    "series": SonarrSensorEntityDescription[list[SonarrSeries]](
        key="series",
        translation_key="series",
        entity_registry_enabled_default=False,
        value_fn=len,
    ),
    "upcoming": SonarrSensorEntityDescription[list[SonarrCalendar]](
        key="upcoming",
        translation_key="upcoming",
        value_fn=len,
    ),
    "wanted": SonarrSensorEntityDescription[SonarrWantedMissing](
        key="wanted",
        translation_key="wanted",
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.totalRecords,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SonarrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sonarr sensors based on a config entry."""
    async_add_entities(
        SonarrSensor(getattr(entry.runtime_data, coordinator_type), description)
        for coordinator_type, description in SENSOR_TYPES.items()
    )


class SonarrSensor(SonarrEntity[SonarrDataT], SensorEntity):
    """Implementation of the Sonarr sensor."""

    coordinator: SonarrDataUpdateCoordinator[SonarrDataT]
    entity_description: SonarrSensorEntityDescription[SonarrDataT]

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
