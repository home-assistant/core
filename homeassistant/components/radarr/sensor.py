"""Support for Radarr."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import cast

from aiopyarr.models.radarr import RadarrCalendar, RadarrMovie
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
from .const import DOMAIN
from .coordinator import RadarrDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="diskspace",
        name="Disk Space",
        native_unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:harddisk",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="upcoming",
        name="Upcoming",
        native_unit_of_measurement="Movies",
        icon="mdi:television",
    ),
    SensorEntityDescription(
        key="wanted",
        name="Wanted",
        native_unit_of_measurement="Movies",
        icon="mdi:television",
    ),
    SensorEntityDescription(
        key="movies",
        name="Movies",
        native_unit_of_measurement="Movies",
        icon="mdi:television",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="commands",
        name="Commands",
        native_unit_of_measurement="Commands",
        icon="mdi:code-braces",
    ),
    SensorEntityDescription(
        key="status",
        name="Status",
        native_unit_of_measurement="Status",
        icon="mdi:information",
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

BYTE_SIZES = [
    DATA_BYTES,
    DATA_KILOBYTES,
    DATA_MEGABYTES,
    DATA_GIGABYTES,
]
# Deprecated in Home Assistant 2022.4
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
    # deprecated in 2022.3
    if "wanted" in config[CONF_MONITORED_CONDITIONS]:
        _LOGGER.warning(
            "Wanted is not a valid condition option. Please remove it from your config"
        )
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
    async_add_entities(
        RadarrSensor(
            hass.data[DOMAIN][entry.entry_id],
            description,
        )
        for description in SENSOR_TYPES
        if description.key != "wanted"
    )


class RadarrSensor(RadarrEntity, SensorEntity):
    """Implementation of the Radarr sensor."""

    coordinator: RadarrDataUpdateCoordinator

    def __init__(
        self,
        coordinator: RadarrDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Create Radarr entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"Radarr {description.name}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}/{description.name}"

    @property
    def extra_state_attributes(self) -> dict[str, StateType | datetime]:
        """Return the state attributes of the sensor."""
        if self.entity_description.key == "commands":
            return {cmd.name: cmd.status for cmd in self.coordinator.commands}
        if self.entity_description.key == "diskspace":
            return self.get_strings(cast(str, self.native_unit_of_measurement))
        if self.entity_description.key == "movies":
            return {to_key(movie): movie.hasFile for movie in self.coordinator.movies}
        if self.entity_description.key == "status":
            return self.coordinator.system_status.attributes
        return {to_key(movie): movie.releaseDate for movie in self.coordinator.calendar}

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if self.entity_description.key == "diskspace":
            space = 0
            for mount in self.coordinator.rootfolder:
                space += mount.freeSpace
            return f"{to_unit(space, cast(str, self.native_unit_of_measurement)):.2f}"
        if self.entity_description.key == "upcoming":
            return len(self.coordinator.calendar)
        if self.entity_description.key == "commands":
            return len(self.coordinator.commands)
        if self.entity_description.key == "movies":
            return len(self.coordinator.movies)
        return self.coordinator.system_status.version

    def get_strings(self, unit: str) -> dict[str, StateType | datetime]:
        """Get diskspace interpolated strings."""
        attrs: dict[str, StateType | datetime] = {}
        last_entry = None
        for mnt in self.coordinator.disk_space:
            for space in self.coordinator.rootfolder:
                if (
                    last_entry != space.freeSpace
                    and mnt.freeSpace * 0.99 <= space.freeSpace <= mnt.freeSpace * 1.01
                ):
                    last_entry = space.freeSpace
                    mnt.freeSpace = space.freeSpace
                    attrs[mnt.path] = "{:.2f}/{:.2f}{} ({:.2f}%)".format(
                        to_unit(space.freeSpace, unit),
                        to_unit(mnt.totalSpace, unit),
                        unit,
                        0
                        if mnt.totalSpace == 0
                        else space.freeSpace / mnt.totalSpace * 100,
                    )
        return attrs


def to_key(movie: RadarrMovie | RadarrCalendar) -> str:
    """Get key."""
    return f"{movie.title} ({movie.year})"


def to_unit(value: int, unit: str = DATA_GIGABYTES) -> float:
    """Convert bytes to give unit."""
    return cast(float, value / 1024 ** BYTE_SIZES.index(unit))
