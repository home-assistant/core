"""Support for Radarr."""
from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Generic

from aiopyarr import Diskspace, RootFolder, SystemStatus
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_PORT,
    CONF_SSL,
    DATA_BYTES,
    DATA_GIGABYTES,
    DATA_KILOBYTES,
    DATA_MEGABYTES,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import RadarrEntity
from .const import DOMAIN
from .coordinator import RadarrDataUpdateCoordinator, T


def get_space(data: list[Diskspace], name: str) -> str:
    """Get space."""
    space = [
        mount.freeSpace / 1024 ** BYTE_SIZES.index(DATA_GIGABYTES)
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
        native_unit_of_measurement=DATA_GIGABYTES,
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
    DATA_BYTES,
    DATA_KILOBYTES,
    DATA_MEGABYTES,
    DATA_GIGABYTES,
]
# Deprecated in Home Assistant 2022.10
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional("days", default=1): cv.string,
        vol.Optional(CONF_HOST, default="localhost"): cv.string,
        vol.Optional("include_paths", default=[]): cv.ensure_list,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=["movies"]): vol.All(
            cv.ensure_list
        ),
        vol.Optional(CONF_PORT, default=7878): cv.port,
        vol.Optional(CONF_SSL, default=False): cv.boolean,
        vol.Optional("unit", default=DATA_GIGABYTES): cv.string,
        vol.Optional("urlbase", default=""): cv.string,
    }
)

PARALLEL_UPDATES = 1


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Radarr platform."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
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
