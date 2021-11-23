"""Support for Radarr."""
from __future__ import annotations

from datetime import datetime
from http import HTTPStatus
import logging
import time
from typing import Any
import requests
import voluptuous as vol
from .coordinator import RadarrDataUpdateCoordinator

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
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from .const import CONF_DAYS, CONF_INCLUDED, CONF_UNIT, CONF_URLBASE, DEFAULT_DAYS, DEFAULT_HOST, DEFAULT_PORT, DEFAULT_UNIT, DEFAULT_URLBASE, DOMAIN

_LOGGER = logging.getLogger(__name__)

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

ENDPOINTS = {
    "diskspace": "{0}://{1}:{2}/{3}api/diskspace",
    "upcoming": "{0}://{1}:{2}/{3}api/calendar?start={4}&end={5}",
    "movies": "{0}://{1}:{2}/{3}api/movie",
    "commands": "{0}://{1}:{2}/{3}api/command",
    "status": "{0}://{1}:{2}/{3}api/system/status",
}

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
    options: dict[str, Any] = dict(entry.options)

    entities = [
        RadarrSensor(
            hass.data[DOMAIN][entry.entry_id],
            entry.entry_id,
            description,
            options,
        )
        for description in SENSOR_TYPES
    ]

    async_add_entities(entities, True)


class RadarrSensor(SensorEntity):
    """Implementation of the Radarr sensor."""

    def __init__(
        self,
        conf: RadarrDataUpdateCoordinator,
        entry_id: str,
        description: SensorEntityDescription,
        options: dict[str, Any],
    ) -> None:
        """Create Radarr entity."""
        self.entity_description = description
        self.coordinator = conf
        self.days = 7
        self.data: list[Any] = []
        self._attr_name = f"Radarr {description.name}"
        self._attr_unique_id = f"{entry_id}/{description.name}"
        #self._attr_available = False

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes of the sensor."""
        attributes = {}
        sensor_type = self.entity_description.key
        #TODO: fix 
        if sensor_type == "upcoming":
            for movie in self.data:
                attributes[to_key(movie)] = get_release_date(movie)
        elif sensor_type == "commands":
            for command in self.data:
                attributes[command["name"]] = command["state"]
        elif sensor_type == "diskspace":
            for data in self.data:
                free_space = to_unit(data["freeSpace"], self.native_unit_of_measurement)
                total_space = to_unit(
                    data["totalSpace"], self.native_unit_of_measurement
                )
                percentage_used = (
                    0 if total_space == 0 else free_space / total_space * 100
                )
                attributes[data["path"]] = "{:.2f}/{:.2f}{} ({:.2f}%)".format(
                    free_space,
                    total_space,
                    self.native_unit_of_measurement,
                    percentage_used,
                )
        elif sensor_type == "movies":
            for movie in self.data:
                attributes[to_key(movie)] = movie["downloaded"]
        elif sensor_type == "status":
            attributes = self.data

        return attributes

    @property
    def native_value(self):
        sensor_type = self.entity_description.key
        #time_zone = dt_util.get_time_zone(self.hass.config.time_zone)
        #start = get_date(time_zone)
        #end = get_date(time_zone, self.days)
        if self.entity_description.key == "diskspace":
            # If included paths are not provided, use all data
            space = 0
            last = None
            #We assume each mapping with the same freespace as the same physical drive
            #for mount in self.coordinator.disk_space:
            #    if mount.freeSpace != last:
            #        space = space + mount.freeSpace
            #        last = mount.freeSpace
            #self._attr_native_value = "{:.2f}".format(to_unit(space, self.native_unit_of_measurement))

        if self.entity_description.key == "upcoming":
            if self.coordinator.calendar is not None:
                return len(self.coordinator.calendar)
        if self.entity_description.key == "movies":
            return len(self.coordinator.movies)
        if self.entity_description.key == "commands":
            if self.coordinator.commands is not None:
                return len(self.coordinator.commands)
        if self.entity_description.key == "status":
            _LOGGER.warning("TESTSENSOR")
            return self.coordinator.system_status.version

        #if res.status_code == HTTPStatus.OK:
        #    if sensor_type in ("upcoming", "movies", "commands"):
        #        self.data = res.json()
        #        self._attr_native_value = len(self.data)
        #    elif sensor_type == "diskspace":
        #        # If included paths are not provided, use all data
        #        if self.included == []:
        #            self.data = res.json()
        #        else:
        #            # Filter to only show lists that are included
        #            self.data = list(
        #                filter(lambda x: x["path"] in self.included, res.json())
        #            )
        #        self._attr_native_value = "{:.2f}".format(
        #            to_unit(
        #                sum(data["freeSpace"] for data in self.data),
        #                self.native_unit_of_measurement,
        #            )
        #        )
        #    elif sensor_type == "status":
        #        self.data = res.json()
        #        self._attr_native_value = self.data["version"]
        #    self._attr_available = True


def get_release_date(data: dict) -> str:
    """Get release date."""
    if not (date := data.get("physicalRelease")):
        date = data.get("inCinemas")
    return date


def to_key(data: dict) -> str:
    """Get key."""
    return "{} ({})".format(data["title"], data["year"])


def to_unit(value: int, unit: str) -> int:
    """Convert bytes to give unit."""
    return value / 1024 ** BYTE_SIZES.index(unit)
