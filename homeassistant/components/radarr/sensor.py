"""Support for Radarr."""
from __future__ import annotations

from collections.abc import Callable
import dataclasses
from datetime import UTC, datetime
from typing import Any, Generic

from aiopyarr import Diskspace, RootFolder, SystemStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RadarrEntity
from .const import DOMAIN
from .coordinator import RadarrDataUpdateCoordinator, T


def get_space(data: list[Diskspace], name: str) -> str:
    """Get space."""
    space = [
        mount.freeSpace / 1024 ** BYTE_SIZES.index(UnitOfInformation.GIGABYTES)
        for mount in data
        if name in mount.path
    ]
    return f"{space[0]:.2f}"


def get_modified_description(
    description: RadarrSensorEntityDescription[T], mount: RootFolder
) -> tuple[RadarrSensorEntityDescription[T], str]:
    """Return modified description and folder name."""
    name = mount.path.rsplit("/")[-1].rsplit("\\")[-1]
    desc = dataclasses.replace(
        description,
        key=f"{description.key}_{name}",
        name=f"{description.name} {name}".capitalize(),
    )
    return desc, name


@dataclasses.dataclass(frozen=True)
class RadarrSensorEntityDescriptionMixIn(Generic[T]):
    """Mixin for required keys."""

    value_fn: Callable[[T, str], str | int | datetime]


@dataclasses.dataclass(frozen=True)
class RadarrSensorEntityDescription(
    SensorEntityDescription, RadarrSensorEntityDescriptionMixIn[T], Generic[T]
):
    """Class to describe a Radarr sensor."""

    description_fn: Callable[
        [RadarrSensorEntityDescription[T], RootFolder],
        tuple[RadarrSensorEntityDescription[T], str] | None,
    ] | None = None


SENSOR_TYPES: dict[str, RadarrSensorEntityDescription[Any]] = {
    "disk_space": RadarrSensorEntityDescription(
        key="disk_space",
        name="Disk space",
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:harddisk",
        value_fn=get_space,
        description_fn=get_modified_description,
    ),
    "movie": RadarrSensorEntityDescription[int](
        key="movies",
        translation_key="movies",
        native_unit_of_measurement="Movies",
        icon="mdi:television",
        entity_registry_enabled_default=False,
        value_fn=lambda data, _: data,
    ),
    "queue": RadarrSensorEntityDescription[int](
        key="queue",
        translation_key="queue",
        native_unit_of_measurement="Movies",
        icon="mdi:download",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data, _: data,
    ),
    "status": RadarrSensorEntityDescription[SystemStatus](
        key="start_time",
        translation_key="start_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data, _: data.startTime.replace(tzinfo=UTC),
    ),
}

BYTE_SIZES = [
    UnitOfInformation.BYTES,
    UnitOfInformation.KILOBYTES,
    UnitOfInformation.MEGABYTES,
    UnitOfInformation.GIGABYTES,
]

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Radarr sensors based on a config entry."""
    coordinators: dict[str, RadarrDataUpdateCoordinator[Any]] = hass.data[DOMAIN][
        entry.entry_id
    ]
    entities: list[RadarrSensor[Any]] = []
    for coordinator_type, description in SENSOR_TYPES.items():
        coordinator = coordinators[coordinator_type]
        if coordinator_type != "disk_space":
            entities.append(RadarrSensor(coordinator, description))
        else:
            entities.extend(
                RadarrSensor(coordinator, *get_modified_description(description, mount))
                for mount in coordinator.data
                if description.description_fn
            )
    async_add_entities(entities)


class RadarrSensor(RadarrEntity[T], SensorEntity):
    """Implementation of the Radarr sensor."""

    coordinator: RadarrDataUpdateCoordinator[T]
    entity_description: RadarrSensorEntityDescription[T]

    def __init__(
        self,
        coordinator: RadarrDataUpdateCoordinator[T],
        description: RadarrSensorEntityDescription[T],
        folder_name: str = "",
    ) -> None:
        """Create Radarr entity."""
        super().__init__(coordinator, description)
        self.folder_name = folder_name

    @property
    def native_value(self) -> str | int | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data, self.folder_name)
