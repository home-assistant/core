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

    value_fn: Callable[[SonarrDataT], StateType]


@dataclass
class SonarrSensorEntityDescription(
    SensorEntityDescription, SonarrSensorEntityDescriptionMixIn[SonarrDataT]
):
    """Class to describe a Sonarr sensor."""

    attributes_fn: Callable[[SonarrDataT], dict[str, str] | None] = lambda _: None


SENSOR_TYPES: dict[str, SonarrSensorEntityDescription[Any]] = {
    "commands": SonarrSensorEntityDescription[list[Command]](
        key="commands",
        name="Sonarr Commands",
        icon="mdi:code-braces",
        native_unit_of_measurement="Commands",
        entity_registry_enabled_default=False,
        value_fn=len,
        attributes_fn=lambda data: {c.name: c.status for c in data},
    ),
    "diskspace": SonarrSensorEntityDescription[list[Diskspace]](
        key="diskspace",
        name="Sonarr Disk Space",
        icon="mdi:harddisk",
        native_unit_of_measurement=DATA_GIGABYTES,
        entity_registry_enabled_default=False,
        value_fn=lambda data: f"{sum(disk.freeSpace for disk in data) / 1024**3:.2f}",
        attributes_fn=lambda data: {
            d.path: f"{d.freeSpace / 1024**3:.2f}/{d.totalSpace / 1024**3:.2f}{DATA_GIGABYTES} ({(d.freeSpace / 1024**3) / (d.totalSpace / 1024**3) * 100:.2f}%)"
            for d in data
        },
    ),
    "queue": SonarrSensorEntityDescription[SonarrQueue](
        key="queue",
        name="Sonarr Queue",
        icon="mdi:download",
        native_unit_of_measurement="Episodes",
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.totalRecords,
        attributes_fn=lambda data: {
            f"{i.series.title} {f'S{i.episode.seasonNumber:02d}E{i.episode.episodeNumber:02d}'}": f"{100 * (1 - (1 if i.size == 0 else i.sizeleft / i.size)):.2f}%"
            for i in data.records
        },
    ),
    "series": SonarrSensorEntityDescription[list[SonarrSeries]](
        key="series",
        name="Sonarr Shows",
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
        name="Sonarr Upcoming",
        icon="mdi:television",
        native_unit_of_measurement="Episodes",
        value_fn=len,
        attributes_fn=lambda data: {
            e.series.title: f"S{e.seasonNumber:02d}E{e.episodeNumber:02d}" for e in data
        },
    ),
    "wanted": SonarrSensorEntityDescription[SonarrWantedMissing](
        key="wanted",
        name="Sonarr Wanted",
        icon="mdi:television",
        native_unit_of_measurement="Episodes",
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.totalRecords,
        attributes_fn=lambda data: {
            f"{i.series.title} {f'S{i.seasonNumber:02d}E{i.episodeNumber:02d}'}": dt_util.as_local(
                i.airDateUtc.replace(tzinfo=dt_util.UTC)
            ).isoformat()
            for i in data.records
        },
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

    coordinator: SonarrDataUpdateCoordinator
    entity_description: SonarrSensorEntityDescription[SonarrDataT]

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the state attributes of the entity."""
        return self.entity_description.attributes_fn(self.coordinator.data)

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
