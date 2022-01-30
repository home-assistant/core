"""Support for Radarr."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any, cast

from aiopyarr import ArrException, RadarrMovie
from aiopyarr.models.host_configuration import PyArrHostConfiguration
from aiopyarr.radarr_client import RadarrClient
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
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.util import dt as dt_util

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


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Radarr platform."""
    host_configuration = PyArrHostConfiguration(
        api_token=config[CONF_API_KEY],
        ipaddress=config[CONF_HOST],
        port=config[CONF_PORT],
        ssl=config[CONF_SSL],
        base_api_path=config[CONF_URLBASE],
    )
    radarr = RadarrClient(
        host_configuration=host_configuration, session=async_get_clientsession(hass)
    )

    try:
        await radarr.async_get_system_status()
    except ArrException as ex:
        raise PlatformNotReady() from ex
    entities = [
        RadarrSensor(config, radarr, description)
        for description in SENSOR_TYPES
        if description.key in config[CONF_MONITORED_CONDITIONS]
    ]
    async_add_entities(entities, True)


class RadarrSensor(SensorEntity):
    """Implementation of the Radarr sensor."""

    def __init__(
        self,
        conf: ConfigType,
        radarr: RadarrClient,
        description: SensorEntityDescription,
    ) -> None:
        """Create Radarr entity."""
        self.entity_description = description
        self.radarr = radarr
        self.included = cast(list, conf.get(CONF_INCLUDED))
        self.days = int(cast(str, conf.get(CONF_DAYS)))
        self.data: Any = None
        self._attr_name = f"Radarr {description.name}"
        if description.key == "diskspace":
            self._attr_native_unit_of_measurement = conf.get(CONF_UNIT)

    @property
    def extra_state_attributes(self) -> dict[str, StateType]:
        """Return the state attributes of the sensor."""
        attributes: dict[str, None | str | int | float] = {}
        if self.entity_description.key == "upcoming":
            return {to_key(movie): release_date(movie) for movie in self.data}
        if self.entity_description.key == "commands":
            return {command.name: command.status for command in self.data}
        if self.entity_description.key == "diskspace":
            for data in self.data:
                free_space = to_unit(data.freeSpace, self.native_unit_of_measurement)
                total_space = to_unit(data.totalSpace, self.native_unit_of_measurement)
                attributes[data.path] = "{:.2f}/{:.2f}{} ({:.2f}%)".format(
                    free_space,
                    total_space,
                    self.native_unit_of_measurement,
                    0 if total_space == 0 else free_space / total_space * 100,
                )
        elif self.entity_description.key == "movies":
            return {to_key(movie): movie.hasFile for movie in self.data}
        if self.entity_description.key == "status":
            return self.data.attributes
        return attributes

    async def async_update(self) -> None:
        """Update the data for the sensor."""
        try:
            if self.entity_description.key == "diskspace":
                data = await self.radarr.async_get_diskspace()
                if len(self.included) > 0:
                    self.data = [datum for datum in data if datum.path in self.included]
                else:
                    self.data = data
                space = sum(mount.freeSpace for mount in self.data)
                self._attr_native_value = (
                    f"{to_unit(space, self.native_unit_of_measurement):.2f}"
                )
            if self.entity_description.key == "upcoming":
                end = dt_util.now() + timedelta(days=self.days)
                self.data = await self.radarr.async_get_calendar(end_date=end)
                self._attr_native_value = len(self.data)
            if self.entity_description.key == "commands":
                self.data = await self.radarr.async_get_commands()
                self._attr_native_value = len(cast(list, self.data))
            if self.entity_description.key == "status":
                self.data = await self.radarr.async_get_system_status()
                self._attr_native_value = self.data.version
            if self.entity_description.key == "movies":
                self.data = await self.radarr.async_get_movies()
                self._attr_native_value = len(cast(list, self.data))
        except ArrException as ex:
            _LOGGER.warning(ex)
        self._attr_available = self.native_value is not None


def release_date(movie: RadarrMovie) -> str:
    """Get release date."""
    date = cast(
        datetime, movie.physicalRelease or movie.digitalRelease or movie.inCinemas
    )
    return date.isoformat()


def to_key(movie: RadarrMovie):
    """Get key."""
    return f"{movie.title} ({movie.year})"


def to_unit(value, unit) -> float:
    """Convert bytes to give unit."""
    return value / 1024 ** BYTE_SIZES.index(unit)
