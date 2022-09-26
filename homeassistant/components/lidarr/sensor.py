"""Support for Lidarr."""
from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Generic

from aiopyarr import LidarrQueueItem, LidarrRootFolder

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_GIGABYTES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import LidarrEntity
from .const import BYTE_SIZES, DOMAIN
from .coordinator import LidarrDataUpdateCoordinator, T


def get_space(data: list[LidarrRootFolder], name: str) -> str:
    """Get space."""
    space = []
    for mount in data:
        if name in mount.path:
            mount.freeSpace = mount.freeSpace if mount.accessible else 0
            space.append(mount.freeSpace / 1024 ** BYTE_SIZES.index(DATA_GIGABYTES))
    return f"{space[0]:.2f}"


def get_modified_description(
    description: LidarrSensorEntityDescription, mount: LidarrRootFolder
) -> tuple[LidarrSensorEntityDescription, str]:
    """Return modified description and folder name."""
    desc = deepcopy(description)
    name = mount.path.rsplit("/")[-1].rsplit("\\")[-1]
    desc.key = f"{description.key}_{name}"
    desc.name = f"{description.name} {name}".capitalize()
    return desc, name


@dataclass
class LidarrSensorEntityDescriptionMixIn(Generic[T]):
    """Mixin for required keys."""

    value_fn: Callable[[T, str], str]


@dataclass
class LidarrSensorEntityDescription(
    SensorEntityDescription, LidarrSensorEntityDescriptionMixIn, Generic[T]
):
    """Class to describe a Lidarr sensor."""

    attributes_fn: Callable[
        [T], dict[str, StateType | datetime] | None
    ] = lambda _: None
    description_fn: Callable[
        [LidarrSensorEntityDescription, LidarrRootFolder],
        tuple[LidarrSensorEntityDescription, str] | None,
    ] = lambda _, __: None


SENSOR_TYPES: dict[str, LidarrSensorEntityDescription] = {
    "disk_space": LidarrSensorEntityDescription(
        key="disk_space",
        name="Disk space",
        native_unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:harddisk",
        value_fn=get_space,
        state_class=SensorStateClass.TOTAL,
        description_fn=get_modified_description,
    ),
    "queue": LidarrSensorEntityDescription(
        key="queue",
        name="Queue",
        native_unit_of_measurement="Albums",
        icon="mdi:download",
        value_fn=lambda data, _: data.totalRecords,
        state_class=SensorStateClass.TOTAL,
        attributes_fn=lambda data: {i.title: queue_str(i) for i in data.records},
    ),
    "wanted": LidarrSensorEntityDescription(
        key="wanted",
        name="Wanted",
        native_unit_of_measurement="Albums",
        icon="mdi:music",
        value_fn=lambda data, _: data.totalRecords,
        state_class=SensorStateClass.TOTAL,
        entity_registry_enabled_default=False,
        attributes_fn=lambda data: {
            album.title: album.artist.artistName for album in data.records
        },
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lidarr sensors based on a config entry."""
    coordinators: dict[str, LidarrDataUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]
    entities = []
    for coordinator_type, description in SENSOR_TYPES.items():
        coordinator = coordinators[coordinator_type]
        if coordinator_type != "disk_space":
            entities.append(LidarrSensor(coordinator, description))
        else:
            entities.extend(
                LidarrSensor(coordinator, *get_modified_description(description, mount))
                for mount in coordinator.data
                if description.description_fn
            )
    async_add_entities(entities)


class LidarrSensor(LidarrEntity, SensorEntity):
    """Implementation of the Lidarr sensor."""

    entity_description: LidarrSensorEntityDescription

    def __init__(
        self,
        coordinator: LidarrDataUpdateCoordinator,
        description: LidarrSensorEntityDescription,
        folder_name: str = "",
    ) -> None:
        """Create Lidarr entity."""
        super().__init__(coordinator, description)
        self.folder_name = folder_name

    @property
    def extra_state_attributes(self) -> dict[str, StateType | datetime] | None:
        """Return the state attributes of the sensor."""
        return self.entity_description.attributes_fn(self.coordinator.data)

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data, self.folder_name)


def queue_str(item: LidarrQueueItem) -> str:
    """Return string description of queue item."""
    if (
        item.sizeleft > 0
        and item.timeleft == "00:00:00"
        or not hasattr(item, "trackedDownloadState")
    ):
        return "stopped"
    return item.trackedDownloadState
