"""Support for Lidarr."""
from __future__ import annotations

from datetime import datetime
from typing import cast

from aiopyarr import Diskspace, LidarrQueueItem
from aiopyarr.models.lidarr import LidarrAlbum, LidarrCalendar

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_GIGABYTES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import LidarrEntity
from .const import BYTE_SIZES, DOMAIN
from .coordinator import LidarrDataUpdateCoordinator

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="commands",
        name="Commands",
        native_unit_of_measurement="Commands",
        icon="mdi:code-braces",
    ),
    SensorEntityDescription(
        key="diskspace",
        name="Disk Space",
        native_unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:harddisk",
    ),
    SensorEntityDescription(
        key="queue",
        name="Queue",
        native_unit_of_measurement="Albums",
        icon="mdi:music",
    ),
    SensorEntityDescription(
        key="status",
        name="Status",
        native_unit_of_measurement="Status",
        icon="mdi:information",
    ),
    SensorEntityDescription(
        key="wanted",
        name="Wanted",
        native_unit_of_measurement="Albums",
        icon="mdi:music",
    ),
    SensorEntityDescription(
        key="upcoming",
        name="Upcoming",
        native_unit_of_measurement="Albums",
        icon="mdi:music",
    ),
)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lidarr sensors based on a config entry."""
    async_add_entities(
        LidarrSensor(hass.data[DOMAIN][entry.entry_id], description)
        for description in SENSOR_TYPES
    )


class LidarrSensor(LidarrEntity, SensorEntity):
    """Implementation of the Lidarr sensor."""

    coordinator: LidarrDataUpdateCoordinator

    def __init__(
        self,
        coordinator: LidarrDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Create Lidarr entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"Lidarr {description.name}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}/{description.name}"

    @property
    def extra_state_attributes(self) -> dict[str, StateType | datetime]:
        """Return the state attributes of the sensor."""
        if self.entity_description.key == "commands":
            return {c.name: c.status for c in self.coordinator.commands}
        if self.entity_description.key == "diskspace":
            return {m.path: mnt_str(m) for m in self.coordinator.disk_space}
        if self.entity_description.key == "queue":
            return {i.title: queue_str(i) for i in self.coordinator.queue.records}
        if self.entity_description.key == "status":
            return self.coordinator.system_status.attributes
        if self.entity_description.key == "upcoming":
            return to_attr(self.coordinator.calendar)
        return to_attr(self.coordinator.wanted.records)

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if self.entity_description.key == "commands":
            return len(self.coordinator.commands)
        if self.entity_description.key == "diskspace":
            fre = sum(m.freeSpace for m in self.coordinator.disk_space)
            return f"{to_unit(fre, cast(str, self.native_unit_of_measurement)):.2f}"
        if self.entity_description.key == "queue":
            return self.coordinator.queue.totalRecords
        if self.entity_description.key == "status":
            return self.coordinator.system_status.version
        if self.entity_description.key == "upcoming":
            return len(self.coordinator.calendar)
        return self.coordinator.wanted.totalRecords


def to_attr(
    albums: list[LidarrCalendar] | list[LidarrAlbum],
) -> dict[str, StateType | datetime]:
    """Get attributes."""
    if len(albums) > 0 and isinstance(albums[0], LidarrCalendar):
        return {
            f"{album.title} ({album.artist.artistName})": album.releaseDate
            for album in albums
        }
    return {
        "{} ({})".format(
            album.title,
            album.artist.artistName,
        ): f"{album.statistics.trackFileCount}/{album.statistics.trackCount}"
        for album in albums
        if hasattr(album.statistics, "trackFileCount")
    }


def to_unit(value: int = 0, unit: str = DATA_GIGABYTES) -> float:
    """Convert bytes to give unit."""
    return value / cast(int, 1024 ** BYTE_SIZES.index(unit))


def mnt_str(mount: Diskspace, unit: str = DATA_GIGABYTES) -> str:
    """Return string description of mount."""
    return "{:.2f}/{:.2f}{} ({:.2f}%)".format(
        to_unit(mount.freeSpace, unit),
        to_unit(mount.totalSpace, unit),
        unit,
        mount.freeSpace / mount.totalSpace * 100 if mount.totalSpace else 0,
    )


def queue_str(item: LidarrQueueItem) -> str:
    """Return string description of queue item."""
    if item.sizeleft > 0 and item.timeleft == "00:00:00":
        return "stopped"
    return item.trackedDownloadState
