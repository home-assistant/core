"""Support for Lidarr."""
from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from aiopyarr import LidarrQueueItem
from aiopyarr.models.lidarr import LidarrAlbum, LidarrCalendar

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_GIGABYTES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import LidarrEntity
from .const import BYTE_SIZES, DEFAULT_NAME, DOMAIN
from .coordinator import LidarrDataUpdateCoordinator


@dataclass
class LidarrSensorEntityDescription(SensorEntityDescription):
    """Class to describe a Lidarr sensor."""

    value: Callable[[LidarrDataUpdateCoordinator, str], Any] = lambda val, _: val


SENSOR_TYPES: tuple[LidarrSensorEntityDescription, ...] = (
    LidarrSensorEntityDescription(
        key="commands",
        name="Commands",
        native_unit_of_measurement="Commands",
        icon="mdi:code-braces",
        value=lambda coordinator, _: coordinator.commands,
    ),
    LidarrSensorEntityDescription(
        key="diskspace",
        name="Disk Space",
        native_unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:harddisk",
        value=lambda coordinator, name: get_space(  # pylint:disable=unnecessary-lambda
            coordinator, name
        ),
    ),
    LidarrSensorEntityDescription(
        key="queue",
        name="Queue",
        native_unit_of_measurement="Albums",
        icon="mdi:music",
        value=lambda coordinator, _: coordinator.queue.totalRecords,
    ),
    LidarrSensorEntityDescription(
        key="status",
        name="Status",
        native_unit_of_measurement="Status",
        icon="mdi:information",
        value=lambda coordinator, _: coordinator.system_status.version,
    ),
    LidarrSensorEntityDescription(
        key="wanted",
        name="Wanted",
        native_unit_of_measurement="Albums",
        icon="mdi:music",
        value=lambda coordinator, _: coordinator.wanted.totalRecords,
    ),
)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lidarr sensors based on a config entry."""
    coordinator: LidarrDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for description in SENSOR_TYPES:
        if description.key == "diskspace":
            for mount in coordinator.disk_space:
                desc = deepcopy(description)
                name = mount.path.rsplit("/")[-1].rsplit("\\")[-1]
                desc.key = f"{description.key}_{name}"
                desc.name = f"{description.name} {name.capitalize()}"
                entities.append(LidarrSensor(coordinator, desc, name))
        else:
            entities.append(LidarrSensor(coordinator, description))
    async_add_entities(entities)


class LidarrSensor(LidarrEntity, SensorEntity):
    """Implementation of the Lidarr sensor."""

    entity_description: LidarrSensorEntityDescription

    def __init__(
        self,
        coordinator: LidarrDataUpdateCoordinator,
        description: LidarrSensorEntityDescription,
        ext_name: str = "",
    ) -> None:
        """Create Lidarr entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"{DEFAULT_NAME} {description.name}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self.ext_name = ext_name

    @property
    def extra_state_attributes(self) -> dict[str, StateType | datetime] | None:
        """Return the state attributes of the sensor."""
        if self.entity_description.key == "queue":
            return {i.title: queue_str(i) for i in self.coordinator.queue.records}
        if self.entity_description.key == "status":
            return self.coordinator.system_status.attributes
        if self.entity_description.key == "wanted":
            return to_attr(self.coordinator.wanted.records)
        return None

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value(self.coordinator, self.ext_name)


def get_space(coordinator: LidarrDataUpdateCoordinator, name: str) -> str:
    """Get space."""
    space = [
        mount.freeSpace / 1024 ** BYTE_SIZES.index(DATA_GIGABYTES)
        for mount in coordinator.disk_space
        if name in mount.path
    ]
    return f"{space[0]:.2f}"


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


def queue_str(item: LidarrQueueItem) -> str:
    """Return string description of queue item."""
    if (
        item.sizeleft > 0
        and item.timeleft == "00:00:00"
        or not hasattr(item, "trackedDownloadState")
    ):
        return "stopped"
    return item.trackedDownloadState
