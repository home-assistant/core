"""Support for Radarr."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timedelta
import logging
from typing import Any

from aiopyarr.exceptions import ArrException
from aiopyarr.models.host_configuration import PyArrHostConfiguration
from aiopyarr.radarr_client import RadarrClient, RadarrMovie
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
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
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_DAYS = "days"
CONF_INCLUDED = "include_paths"
CONF_UNIT = "unit"
CONF_URLBASE = "urlbase"

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 7878
DEFAULT_URLBASE = ""
DEFAULT_DAYS = "1"
DEFAULT_UNIT = DATA_GIGABYTES

SCAN_INTERVAL = timedelta(minutes=10)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="diskspace",
        name="Disk Space",
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

# Support to Yottabytes for the future, why not
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
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_DAYS, default=DEFAULT_DAYS): vol.Coerce(int),
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


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Radarr platform."""
    conditions = config[CONF_MONITORED_CONDITIONS]
    entities = [
        RadarrSensor(hass, config, description)
        for description in SENSOR_TYPES
        if description.key in conditions
    ]
    async_add_entities(entities, True)


class RadarrSensor(SensorEntity):
    """Implementation of the Radarr sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        conf: ConfigType,
        description: SensorEntityDescription,
    ) -> None:
        """Create Radarr entity."""
        self.entity_description = description
        url_base = conf.get(CONF_URLBASE)
        if url_base:
            url_base = f"{url_base.strip('/')}/"
        self.host_config = PyArrHostConfiguration(
            api_token=conf[CONF_API_KEY],
            hostname=conf[CONF_HOST],
            port=conf[CONF_PORT],
            ssl=conf[CONF_SSL],
            base_api_path=url_base,
        )
        self.client = RadarrClient(
            self.host_config, session=async_get_clientsession(hass)
        )
        self.included = conf.get(CONF_INCLUDED)
        self.days = conf[CONF_DAYS]
        self.data: dict[str, Any] = {}

        self._attr_name = f"Radarr {description.name}"
        self._attr_available = True
        if description.key == "diskspace":
            self._attr_native_unit_of_measurement = conf[CONF_UNIT]

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return extra state attributes for entity."""
        sensor_type = self.entity_description.key
        if sensor_type == "diskspace":
            data = {}
            for volume in self.data[sensor_type]:
                free_space = to_unit(volume.freeSpace, self.native_unit_of_measurement)
                total_space = to_unit(
                    volume.totalSpace, self.native_unit_of_measurement
                )
                percentage_used = (
                    0 if total_space == 0 else free_space / total_space * 100
                )
                data[volume.path] = "{:.2f}/{:.2f}{} ({:.2f}%)".format(
                    free_space,
                    total_space,
                    self.native_unit_of_measurement,
                    percentage_used,
                )
            return data

        if sensor_type == "upcoming":
            return {
                movie_title(movie): get_release_date(movie)
                for movie in self.data[sensor_type]
            }

        if sensor_type == "movies":
            return {
                movie_title(movie): movie.attributes.get("hasFile", False)
                for movie in self.data[sensor_type]
            }

        if sensor_type == "commands":
            return {command.name: command.status for command in self.data[sensor_type]}

        if sensor_type == "status":
            return self.data[sensor_type].attributes

        return {}

    @property
    def native_value(self) -> str | int | None:
        """Return the native value of the entity."""
        sensor_type = self.entity_description.key
        if sensor_type == "diskspace":
            return "{:.2f}".format(
                to_unit(
                    sum(volume.freeSpace for volume in self.data[sensor_type]),
                    self.native_unit_of_measurement,
                )
            )

        if sensor_type == "upcoming":
            return len(self.data[sensor_type])

        if sensor_type == "movies":
            return len(self.data[sensor_type])

        if sensor_type == "commands":
            return len(self.data[sensor_type])

        if sensor_type == "status":
            return self.data[sensor_type].version

        return None

    async def async_update(self) -> None:
        """Update the sensor."""
        sensor_type = self.entity_description.key
        start = datetime.combine(date.today(), datetime.min.time())
        end = start + timedelta(days=self.days)
        try:
            if sensor_type == "diskspace":
                self.data[sensor_type] = await self.client.async_get_diskspace()
            elif sensor_type == "upcoming":
                self.data[sensor_type] = await self.client.async_get_calendar(
                    start, end
                )
            elif sensor_type == "movies":
                self.data[sensor_type] = await self.client.async_get_movies()
                if not isinstance(self.data[sensor_type], list):
                    self.data[sensor_type] = [self.data[sensor_type]]
            elif sensor_type == "commands":
                self.data[sensor_type] = await self.client.async_get_commands()
                if not isinstance(self.data[sensor_type], list):
                    self.data[sensor_type] = [self.data[sensor_type]]
            elif sensor_type == "status":
                self.data[sensor_type] = await self.client.async_get_system_status()
            else:
                raise ValueError(f"Unknown sensor type {sensor_type}")
        except ArrException as err:
            if self._attr_available:
                _LOGGER.warning(err)
            self._attr_available = False
        else:
            self._attr_available = True
            if sensor_type == "diskspace" and self.included:
                self.data[sensor_type] = [
                    volume
                    for volume in self.data[sensor_type]
                    if volume.path in self.included
                ]


def get_release_date(movie: RadarrMovie) -> str | None:
    """Get release date."""
    for key in ("digitalRelease", "physicalRelease", "inCinemas"):
        if key in movie.attributes:
            return getattr(movie, key).isoformat()
    return None


def movie_title(movie: RadarrMovie) -> str:
    """Get key."""
    return f"{movie.title} ({movie.year})"


def to_unit(value, unit):
    """Convert bytes to give unit."""
    return value / 1024 ** BYTE_SIZES.index(unit)
