"""Support for Radarr."""
from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType

from . import RadarrEntity
from .const import DEFAULT_NAME, DOMAIN
from .coordinator import RadarrDataUpdateCoordinator


@dataclass
class RadarrSensorEntityDescription(SensorEntityDescription):
    """Class to describe a Radarr sensor."""

    value: Callable[[RadarrDataUpdateCoordinator, str], Any] = lambda val, _: val


SENSOR_TYPES: tuple[RadarrSensorEntityDescription, ...] = (
    RadarrSensorEntityDescription(
        key="diskspace",
        name="Disk Space",
        native_unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:harddisk",
        value=lambda coordinator, name: get_space(  # pylint:disable=unnecessary-lambda
            coordinator, name
        ),
    ),
    RadarrSensorEntityDescription(
        key="movies",
        name="Movies",
        native_unit_of_measurement="Movies",
        icon="mdi:television",
        entity_registry_enabled_default=False,
        value=lambda coordinator, _: coordinator.movies,
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

BYTE_SIZES = [
    DATA_BYTES,
    DATA_KILOBYTES,
    DATA_MEGABYTES,
    DATA_GIGABYTES,
]
# Deprecated in Home Assistant 2022.7
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional("days", default=1): cv.string,
        vol.Optional(CONF_HOST, default="localhost"): cv.string,
        vol.Optional("include_paths", default=[]): cv.ensure_list,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=["movies"]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
        vol.Optional(CONF_PORT, default=7878): cv.port,
        vol.Optional(CONF_SSL, default=False): cv.boolean,
        vol.Optional("unit", default=DATA_GIGABYTES): cv.string,
        vol.Optional("urlbase", default=""): cv.string,
    }
)

PARALLEL_UPDATES = 1


def setup_platform(
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
    coordinator: RadarrDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for description in SENSOR_TYPES:
        if description.key == "diskspace":
            for mount in coordinator.disk_space:
                desc = deepcopy(description)
                name = mount.path.rsplit("/")[-1].rsplit("\\")[-1]
                desc.key = f"{description.key}_{name}"
                desc.name = f"{description.name} {name.capitalize()}"
                entities.append(RadarrSensor(coordinator, desc, name))
        else:
            entities.append(RadarrSensor(coordinator, description))
    async_add_entities(entities)


class RadarrSensor(RadarrEntity, SensorEntity):
    """Implementation of the Radarr sensor."""

    entity_description: RadarrSensorEntityDescription

    def __init__(
        self,
        coordinator: RadarrDataUpdateCoordinator,
        description: RadarrSensorEntityDescription,
        folder_name: str = "",
    ) -> None:
        """Create Radarr entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"{DEFAULT_NAME} {description.name}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self.folder_name = folder_name

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value(self.coordinator, self.folder_name)


def get_space(coordinator: RadarrDataUpdateCoordinator, name: str) -> str:
    """Get space."""
    space = [
        mount.freeSpace / 1024 ** BYTE_SIZES.index(DATA_GIGABYTES)
        for mount in coordinator.disk_space
        if name in mount.path
    ]
    return f"{space[0]:.2f}"
