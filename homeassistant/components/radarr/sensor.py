"""Support for Radarr."""
from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Generic

from aiopyarr import Diskspace, RootFolder, SystemStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

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
    desc = deepcopy(description)
    name = mount.path.rsplit("/")[-1].rsplit("\\")[-1]
    desc.key = f"{description.key}_{name}"
    desc.name = f"{description.name} {name}".capitalize()
    return desc, name


@dataclass
class RadarrSensorEntityDescriptionMixIn(Generic[T]):
    """Mixin for required keys."""

    value_fn: Callable[[T, str], str | int | datetime]


@dataclass
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
        name="Movies",
        native_unit_of_measurement="Movies",
        icon="mdi:television",
        entity_registry_enabled_default=False,
        value_fn=lambda data, _: data,
    ),
    "status": RadarrSensorEntityDescription[SystemStatus](
        key="start_time",
        name="Start time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data, _: data.startTime.replace(tzinfo=timezone.utc),
    ),
}

BYTE_SIZES = [
    UnitOfInformation.BYTES,
    UnitOfInformation.KILOBYTES,
    UnitOfInformation.MEGABYTES,
    UnitOfInformation.GIGABYTES,
]

PARALLEL_UPDATES = 1


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Radarr platform."""
    async_create_issue(
        hass,
        DOMAIN,
        "removed_yaml",
        breaks_in_ha_version="2022.12.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="removed_yaml",
    )


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
