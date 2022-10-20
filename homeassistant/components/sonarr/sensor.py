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

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_GIGABYTES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .coordinator import SonarrDataT, SonarrDataUpdateCoordinator
from .entity import SonarrEntity


@dataclass
class SonarrSensorEntityDescriptionMixIn(Generic[SonarrDataT]):
    """Mixin for Sonarr sensor."""

    attributes_fn: Callable[[SonarrDataT], dict[str, str]]
    value_fn: Callable[[SonarrDataT], StateType]


@dataclass
class SonarrSensorEntityDescription(
    SensorEntityDescription, SonarrSensorEntityDescriptionMixIn[SonarrDataT]
):
    """Class to describe a Sonarr sensor."""


def get_disk_space_attr(disks: list[Diskspace]) -> dict[str, str]:
    """Create the attributes for disk space."""
    attrs: dict[str, str] = {}
    for disk in disks:
        free = disk.freeSpace / 1024**3
        total = disk.totalSpace / 1024**3
        usage = free / total * 100
        attrs[disk.path] = f"{free:.2f}/{total:.2f}{DATA_GIGABYTES} ({usage:.2f}%)"
    return attrs


def get_queue_attr(queue: SonarrQueue) -> dict[str, str]:
    """Create the attributes for series queue."""
    attrs: dict[str, str] = {}
    for item in queue.records:
        remaining = 1 if item.size == 0 else item.sizeleft / item.size
        remaining_pct = 100 * (1 - remaining)
        identifier = (
            f"S{item.episode.seasonNumber:02d}E{item.episode. episodeNumber:02d}"
        )
        attrs[f"{item.series.title} {identifier}"] = f"{remaining_pct:.2f}%"
    return attrs


def get_wanted_attr(wanted: SonarrWantedMissing) -> dict[str, str]:
    """Create the attributes for missing series."""
    attrs: dict[str, str] = {}
    for item in wanted.records:
        identifier = f"S{item.seasonNumber:02d}E{item.episodeNumber:02d}"

        name = f"{item.series.title} {identifier}"
        attrs[name] = dt_util.as_local(
            item.airDateUtc.replace(tzinfo=dt_util.UTC)
        ).isoformat()
    return attrs


SENSOR_TYPES: dict[str, SonarrSensorEntityDescription[Any]] = {
    "commands": SonarrSensorEntityDescription[list[Command]](
        key="commands",
        name="Commands",
        icon="mdi:code-braces",
        native_unit_of_measurement="Commands",
        entity_registry_enabled_default=False,
        value_fn=len,
        attributes_fn=lambda data: {c.name: c.status for c in data},
    ),
    "diskspace": SonarrSensorEntityDescription[list[Diskspace]](
        key="diskspace",
        name="Disk space",
        icon="mdi:harddisk",
        native_unit_of_measurement=DATA_GIGABYTES,
        entity_registry_enabled_default=False,
        value_fn=lambda data: f"{sum(disk.freeSpace for disk in data) / 1024**3:.2f}",
        attributes_fn=get_disk_space_attr,
    ),
    "queue": SonarrSensorEntityDescription[SonarrQueue](
        key="queue",
        name="Queue",
        icon="mdi:download",
        native_unit_of_measurement="Episodes",
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.totalRecords,
        attributes_fn=get_queue_attr,
    ),
    "series": SonarrSensorEntityDescription[list[SonarrSeries]](
        key="series",
        name="Shows",
        icon="mdi:television",
        native_unit_of_measurement="Series",
        entity_registry_enabled_default=False,
        value_fn=len,
        attributes_fn=lambda data: {
            i.title: f"{getattr(i.statistics,'episodeFileCount', 0)}/{getattr(i.statistics, 'episodeCount', 0)} Episodes"
            for i in data
        },
    ),
    "upcoming": SonarrSensorEntityDescription[list[SonarrCalendar]](
        key="upcoming",
        name="Upcoming",
        icon="mdi:television",
        native_unit_of_measurement="Episodes",
        value_fn=len,
        attributes_fn=lambda data: {
            e.series.title: f"S{e.seasonNumber:02d}E{e.episodeNumber:02d}" for e in data
        },
    ),
    "wanted": SonarrSensorEntityDescription[SonarrWantedMissing](
        key="wanted",
        name="Wanted",
        icon="mdi:television",
        native_unit_of_measurement="Episodes",
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.totalRecords,
        attributes_fn=get_wanted_attr,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sonarr sensors based on a config entry."""
    coordinators: dict[str, SonarrDataUpdateCoordinator[Any]] = hass.data[DOMAIN][
        entry.entry_id
    ]
    async_add_entities(
        SonarrSensor(coordinators[coordinator_type], description)
        for coordinator_type, description in SENSOR_TYPES.items()
    )


class SonarrSensor(SonarrEntity[SonarrDataT], SensorEntity):
    """Implementation of the Sonarr sensor."""

    coordinator: SonarrDataUpdateCoordinator[SonarrDataT]
    entity_description: SonarrSensorEntityDescription[SonarrDataT]

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the state attributes of the entity."""
        return self.entity_description.attributes_fn(self.coordinator.data)

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
