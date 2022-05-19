"""Support for Radarr."""
from __future__ import annotations

from datetime import datetime, timedelta
from http import HTTPStatus
import logging
import time
from typing import Any

import requests
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
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
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
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Radarr platform."""
    conditions = config[CONF_MONITORED_CONDITIONS]
    # deprecated in 2022.3
    entities = [
        RadarrSensor(hass, config, description)
        for description in SENSOR_TYPES
        if description.key in conditions
    ]
    add_entities(entities, True)


class RadarrSensor(SensorEntity):
    """Implementation of the Radarr sensor."""

    def __init__(self, hass, conf, description: SensorEntityDescription):
        """Create Radarr entity."""
        self.entity_description = description

        self.conf = conf
        self.host = conf.get(CONF_HOST)
        self.port = conf.get(CONF_PORT)
        self.urlbase = conf.get(CONF_URLBASE)
        if self.urlbase:
            self.urlbase = f"{self.urlbase.strip('/')}/"
        self.apikey = conf.get(CONF_API_KEY)
        self.included = conf.get(CONF_INCLUDED)
        self.days = int(conf.get(CONF_DAYS))
        self.ssl = "https" if conf.get(CONF_SSL) else "http"
        self.data: list[Any] = []
        self._attr_name = f"Radarr {description.name}"
        if description.key == "diskspace":
            self._attr_native_unit_of_measurement = conf.get(CONF_UNIT)
        self._attr_available = False

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        attributes = {}
        sensor_type = self.entity_description.key
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

    def update(self):
        """Update the data for the sensor."""
        sensor_type = self.entity_description.key
        time_zone = dt_util.get_time_zone(self.hass.config.time_zone)
        start = get_date(time_zone)
        end = get_date(time_zone, self.days)
        try:
            res = requests.get(
                ENDPOINTS[sensor_type].format(
                    self.ssl, self.host, self.port, self.urlbase, start, end
                ),
                headers={"X-Api-Key": self.apikey},
                timeout=10,
            )
        except OSError:
            _LOGGER.warning("Host %s is not available", self.host)
            self._attr_available = False
            self._attr_native_value = None
            return

        if res.status_code == HTTPStatus.OK:
            if sensor_type in ("upcoming", "movies", "commands"):
                self.data = res.json()
                self._attr_native_value = len(self.data)
            elif sensor_type == "diskspace":
                # If included paths are not provided, use all data
                if self.included == []:
                    self.data = res.json()
                else:
                    # Filter to only show lists that are included
                    self.data = list(
                        filter(lambda x: x["path"] in self.included, res.json())
                    )
                self._attr_native_value = "{:.2f}".format(
                    to_unit(
                        sum(data["freeSpace"] for data in self.data),
                        self.native_unit_of_measurement,
                    )
                )
            elif sensor_type == "status":
                self.data = res.json()
                self._attr_native_value = self.data["version"]
            self._attr_available = True


def get_date(zone, offset=0):
    """Get date based on timezone and offset of days."""
    day = 60 * 60 * 24
    return datetime.date(datetime.fromtimestamp(time.time() + day * offset, tz=zone))


def get_release_date(data):
    """Get release date."""
    if not (date := data.get("physicalRelease")):
        date = data.get("inCinemas")
    return date


def to_key(data):
    """Get key."""
    return "{} ({})".format(data["title"], data["year"])


def to_unit(value, unit):
    """Convert bytes to give unit."""
    return value / 1024 ** BYTE_SIZES.index(unit)
