"""Support for Radarr."""
from __future__ import annotations

from typing import cast

from aiopyarr.models.radarr import RadarrMovie
import voluptuous as vol

from homeassistant.components.radarr import RadarrEntity
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
    DATA_EXABYTES,
    DATA_GIGABYTES,
    DATA_KILOBYTES,
    DATA_MEGABYTES,
    DATA_PETABYTES,
    DATA_TERABYTES,
    DATA_YOTTABYTES,
    DATA_ZETTABYTES,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType

from .const import (
    CONF_DAYS,
    CONF_INCLUDED,
    CONF_UNIT,
    CONF_URLBASE,
    DEFAULT_DAYS,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_UNIT,
    DEFAULT_URLBASE,
    DOMAIN,
)
from .coordinator import RadarrDataUpdateCoordinator

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="diskspace",
        name="Disk Space",
        native_unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:harddisk",
    ),
    SensorEntityDescription(
        key="upcoming",
        name="Upcoming",
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
    DATA_TERABYTES,
    DATA_PETABYTES,
    DATA_EXABYTES,
    DATA_ZETTABYTES,
    DATA_YOTTABYTES,
]
# Deprecated in Home Assistant 2022.1
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_DAYS, default=DEFAULT_DAYS): cv.string,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_INCLUDED, default=[]): cv.ensure_list,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=["movies"]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SSL, default=False): cv.boolean,
        vol.Optional(CONF_UNIT, default=DEFAULT_UNIT): vol.In(BYTE_SIZES),
        vol.Optional(CONF_URLBASE, default=DEFAULT_URLBASE): cv.string,
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
    entities = [
        RadarrSensor(
            hass.data[DOMAIN][entry.entry_id],
            description,
            entry.entry_id,
        )
        for description in SENSOR_TYPES
    ]

    async_add_entities(entities, True)


class RadarrSensor(RadarrEntity, SensorEntity):
    """Implementation of the Radarr sensor."""

    def __init__(
        self,
        coordinator: RadarrDataUpdateCoordinator,
        description: SensorEntityDescription,
        entry_id: str,
    ) -> None:
        """Create Radarr entity."""
        super().__init__(coordinator, entry_id)
        self.entity_description = description
        self.coordinator = coordinator
        self._attr_name = f"Radarr {description.name}"
        self._attr_unique_id = f"{entry_id}/{description.name}"

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes of the sensor."""
        attributes = {}
        if self.entity_description.key == "upcoming":
            for movie in self.coordinator.calendar:  # type: ignore
                attributes[to_key(movie)] = movie.physicalRelease or movie.inCinemas
        elif self.entity_description.key == "commands":
            for command in self.coordinator.commands:  # type: ignore
                attributes[command.name] = command.status
        elif self.entity_description.key == "diskspace":
            for key, item in self.get_mapped_capacity().items():
                attributes[key] = item
        elif (
            self.entity_description.key == "movies"
            and self.coordinator.movies is not None  # type: ignore
        ):
            for movie in self.coordinator.movies:  # type: ignore
                attributes[to_key(movie)] = movie.hasFile
        elif self.entity_description.key == "status":
            attributes = self.coordinator.system_status.attributes  # type: ignore
        return attributes

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        value = None
        if self.entity_description.key == "diskspace" and self.coordinator.disk_space:  # type: ignore
            space = 0
            for mount in self.coordinator.disk_space:  # type: ignore
                space = space + mount.freeSpace
            value = f"{to_unit(space, cast(str, self.native_unit_of_measurement)):.2f}"

        elif self.entity_description.key == "upcoming":
            value = str(len(self.coordinator.calendar))  # type: ignore
        elif self.entity_description.key == "commands":
            value = str(len(self.coordinator.commands))  # type: ignore
        elif self.entity_description.key == "status":
            value = self.coordinator.system_status.version  # type: ignore
        elif self.entity_description.key == "movies":
            self.coordinator.movies_count_enabled = True  # type: ignore
            if self.coordinator.movies:  # type: ignore
                value = str(len(self.coordinator.movies))  # type: ignore
        return value

    def get_mapped_capacity(self) -> dict[str, str]:
        """Get mapped mount capacity."""
        # The below logic attempts to match total space with free space
        attrs = {}
        if (
            self.coordinator.get_space  # type: ignore
            and len(self.coordinator.agg_space) != 0  # type: ignore
            and self.native_unit_of_measurement
        ):
            for mount in self.coordinator.disk_space:  # type: ignore
                for key, item in self.coordinator.agg_space.items():  # type: ignore
                    if (
                        item <= mount.freeSpace * 1.01
                        and item >= mount.freeSpace * 0.99
                    ):
                        self.coordinator.agg_space[key] = mount.freeSpace  # type: ignore
                        attrs[mount.path] = "{:.2f}/{:.2f}{} ({:.2f}%)".format(
                            to_unit(mount.freeSpace, self.native_unit_of_measurement),
                            to_unit(key, self.native_unit_of_measurement),
                            self.native_unit_of_measurement,
                            0 if key == 0 else mount.freeSpace / key * 100,
                        )
                    else:
                        attrs[mount.path] = "{:.2f} {}".format(
                            to_unit(mount.freeSpace, self.native_unit_of_measurement),
                            self.native_unit_of_measurement,
                        )
        return attrs


def to_key(movie: RadarrMovie) -> str:
    """Get key."""
    return f"{movie.title} ({movie.year})"


def to_unit(value: int, unit: str = DATA_GIGABYTES) -> float:
    """Convert bytes to give unit."""
    return value / 1024 ** BYTE_SIZES.index(unit)
