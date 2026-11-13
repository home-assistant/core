"""Support for Radarr."""

from collections.abc import Callable
import dataclasses
from datetime import UTC, datetime
from typing import Any, Generic, override

from aiopyarr import Diskspace, RootFolder, SystemStatus

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import RadarrConfigEntry, RadarrDataUpdateCoordinator, T
from .entity import RadarrEntity


def get_space(data: list[Diskspace], path: str) -> str:
    """Get space."""
    space = [
        mount.freeSpace / 1024 ** BYTE_SIZES.index(UnitOfInformation.GIGABYTES)
        for mount in data
        if mount.path == path
    ]
    return f"{space[0]:.2f}"


def get_folder_name(mount: RootFolder) -> str:
    """Return the last part of a root folder path."""
    return mount.path.rsplit("/")[-1].rsplit("\\")[-1]


def get_modified_description(
    description: RadarrSensorEntityDescription[T], mount: RootFolder
) -> tuple[RadarrSensorEntityDescription[T], str]:
    """Return modified description and folder path."""
    name = get_folder_name(mount)
    desc = dataclasses.replace(
        description,
        key=f"root_folder_{mount.id}_{description.key}",
        name=f"{description.name} {name}".capitalize(),
    )
    return desc, mount.path


@callback
def async_migrate_disk_space_unique_ids(
    hass: HomeAssistant, entry: RadarrConfigEntry, mounts: list[RootFolder]
) -> None:
    """Migrate disk space sensors from folder name to root folder ID unique IDs."""
    entity_registry = er.async_get(hass)
    seen: set[str] = set()
    for mount in mounts:
        name = get_folder_name(mount)
        # The folder name ID belonged to the first root folder with that name
        if name in seen:
            continue
        seen.add(name)
        old_unique_id = f"{entry.entry_id}_disk_space_{name}"
        new_unique_id = f"{entry.entry_id}_root_folder_{mount.id}_disk_space"
        if (
            entity_id := entity_registry.async_get_entity_id(
                SENSOR_DOMAIN, DOMAIN, old_unique_id
            )
        ) and not entity_registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, new_unique_id
        ):
            entity_registry.async_update_entity(entity_id, new_unique_id=new_unique_id)


@dataclasses.dataclass(frozen=True)
class RadarrSensorEntityDescriptionMixIn(Generic[T]):  # noqa: UP046
    """Mixin for required keys."""

    value_fn: Callable[[T, str], str | int | datetime]


@dataclasses.dataclass(frozen=True)
class RadarrSensorEntityDescription(
    SensorEntityDescription,
    RadarrSensorEntityDescriptionMixIn[T],
    Generic[T],  # noqa: UP046
):
    """Class to describe a Radarr sensor."""

    description_fn: (
        Callable[
            [RadarrSensorEntityDescription[T], RootFolder],
            tuple[RadarrSensorEntityDescription[T], str] | None,
        ]
        | None
    ) = None


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
        entity_registry_enabled_default=False,
        value_fn=lambda data, _: data,
    ),
    "queue": RadarrSensorEntityDescription[int](
        key="queue",
        translation_key="queue",
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
    entry: RadarrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Radarr sensors based on a config entry."""
    entities: list[RadarrSensor[Any]] = []
    for coordinator_type, description in SENSOR_TYPES.items():
        coordinator = getattr(entry.runtime_data, coordinator_type)
        if coordinator_type != "disk_space":
            entities.append(RadarrSensor(coordinator, description))
        else:
            async_migrate_disk_space_unique_ids(hass, entry, coordinator.data)
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
    @override
    def native_value(self) -> str | int | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data, self.folder_name)
