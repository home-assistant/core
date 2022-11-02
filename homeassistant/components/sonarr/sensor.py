"""Support for Sonarr sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic

from aiopyarr import (
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


SENSOR_TYPES: dict[str, SonarrSensorEntityDescription[Any]] = {
    "commands": SonarrSensorEntityDescription(
        key="commands",
        name="Commands",
        icon="mdi:code-braces",
        native_unit_of_measurement="Commands",
        entity_registry_enabled_default=False,
        value_fn=len,
    ),
    "diskspace": SonarrSensorEntityDescription[list[Diskspace]](
        key="diskspace",
        name="Disk space",
        icon="mdi:harddisk",
        native_unit_of_measurement=DATA_GIGABYTES,
        entity_registry_enabled_default=False,
        value_fn=lambda data: f"{sum(disk.freeSpace for disk in data) / 1024**3:.2f}",
    ),
    "queue": SonarrSensorEntityDescription[SonarrQueue](
        key="queue",
        name="Queue",
        icon="mdi:download",
        native_unit_of_measurement="Episodes",
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.totalRecords,
    ),
    "series": SonarrSensorEntityDescription[list[SonarrSeries]](
        key="series",
        name="Shows",
        icon="mdi:television",
        native_unit_of_measurement="Series",
        entity_registry_enabled_default=False,
        value_fn=len,
    ),
    "upcoming": SonarrSensorEntityDescription[list[SonarrCalendar]](
        key="upcoming",
        name="Upcoming",
        icon="mdi:television",
        native_unit_of_measurement="Episodes",
        value_fn=len,
    ),
    "wanted": SonarrSensorEntityDescription[SonarrWantedMissing](
        key="wanted",
        name="Wanted",
        icon="mdi:television",
        native_unit_of_measurement="Episodes",
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.totalRecords,
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
        attrs = {}
        key = self.entity_description.key
        data = self.coordinator.data

        if key == "diskspace":
            for disk in data:
                free = disk.freeSpace / 1024**3
                total = disk.totalSpace / 1024**3
                usage = free / total * 100

                attrs[
                    disk.path
                ] = f"{free:.2f}/{total:.2f}{self.unit_of_measurement} ({usage:.2f}%)"
        elif key == "commands":
            for command in data:
                attrs[command.name] = command.status
        elif key == "queue":
            for item in data.records:
                remaining = 1 if item.size == 0 else item.sizeleft / item.size
                remaining_pct = 100 * (1 - remaining)
                identifier = f"S{item.episode.seasonNumber:02d}E{item.episode. episodeNumber:02d}"

                name = f"{item.series.title} {identifier}"
                attrs[name] = f"{remaining_pct:.2f}%"
        elif key == "series":
            for item in data:
                stats = item.statistics
                attrs[
                    item.title
                ] = f"{getattr(stats,'episodeFileCount', 0)}/{getattr(stats, 'episodeCount', 0)} Episodes"
        elif key == "upcoming":
            for episode in data:
                identifier = f"S{episode.seasonNumber:02d}E{episode.episodeNumber:02d}"
                attrs[episode.series.title] = identifier
        elif key == "wanted":
            for item in data.records:
                identifier = f"S{item.seasonNumber:02d}E{item.episodeNumber:02d}"

                name = f"{item.series.title} {identifier}"
                attrs[name] = dt_util.as_local(
                    item.airDateUtc.replace(tzinfo=dt_util.UTC)
                ).isoformat()

        return attrs

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
