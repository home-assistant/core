"""Support for Sonarr."""
from datetime import datetime
from typing import Dict, Optional, Union
import logging

from pytz import timezone
from sonarr import Sonarr, SonarrError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
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
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

CONF_DAYS = "days"
CONF_INCLUDED = "include_paths"
CONF_UNIT = "unit"
CONF_URLBASE = "urlbase"

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8989
DEFAULT_URLBASE = ""
DEFAULT_DAYS = "1"
DEFAULT_UNIT = DATA_GIGABYTES

SENSOR_TYPES = {
    "diskspace": ["Disk Space", DATA_GIGABYTES, "mdi:harddisk"],
    "queue": ["Queue", "Episodes", "mdi:download"],
    "upcoming": ["Upcoming", "Episodes", "mdi:television"],
    "wanted": ["Wanted", "Episodes", "mdi:television"],
    "series": ["Series", "Shows", "mdi:television"],
    "commands": ["Commands", "Commands", "mdi:code-braces"],
    "status": ["Status", "Status", "mdi:information"],
}

ENDPOINTS = {
    "diskspace": "{0}://{1}:{2}/{3}api/diskspace",
    "queue": "{0}://{1}:{2}/{3}api/queue",
    "upcoming": "{0}://{1}:{2}/{3}api/calendar?start={4}&end={5}",
    "wanted": "{0}://{1}:{2}/{3}api/wanted/missing",
    "series": "{0}://{1}:{2}/{3}api/series",
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

PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_DAYS, default=DEFAULT_DAYS): cv.string,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_INCLUDED, default=[]): cv.ensure_list,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=["upcoming"]): vol.All(
            cv.ensure_list, [vol.In(list(SENSOR_TYPES))]
        ),
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SSL, default=False): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=False): cv.boolean,
        vol.Optional(CONF_UNIT, default=DEFAULT_UNIT): vol.In(BYTE_SIZES),
        vol.Optional(CONF_URLBASE, default=DEFAULT_URLBASE): cv.string,
    }
)


def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Sonarr platform."""
    conditions = config.get(CONF_MONITORED_CONDITIONS)

    sonarr = Sonarr(
        host=config[CONF_HOST],
        api_key=config[CONF_API_KEY],
        base_path=config[CONF_URLBASE],
        port=config[CONF_PORT],
        tls=config[CONF_SSL],
    )

    entities = [
        SonarrCommandsSensor(sonarr),
        SonarrDiskspaceSensor(sonarr),
        SonarrQueueSensor(sonarr),
        SonarrSeriesSensor(sonarr),
        SonarrUpcomingSensor(sonarr),
        SonarrWantedSensor(sonarr),
    ]

    async_add_entities(entities, True)


class SonarrEntity(Entity):
    """Defines a base Sonarr entity."""

    def __init__(
        self,
        *,
        sonarr: Sonarr,
        name: str,
        icon: str,
        enabled_default: bool = True,
    ) -> None:
        """Initialize the Sonar entity."""
        self._enabled_default = enabled_default
        self._icon = icon
        self._name = name
        self.sonarr = sonarr

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the mdi icon of the entity."""
        return self._icon

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._enabled_default

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about the application."""
        if self.unique_id is None:
            return None

        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self.sonarr.app.info.uuid)},
            ATTR_NAME: "Activity Sensor",
            ATTR_MANUFACTURER: "Sonarr",
            ATTR_SOFTWARE_VERSION: self.sonarr.app.info.version,
        }


class SonarrSensor(SonarrEntity):
    """Implementation of the Sonarr sensor."""

    def __init__(
        self,
        *,
        sonarr: Sonarr,
        enabled_default: bool = True,
        entry_id: str,
        icon: str,
        key: str,
        name: str,
        unit_of_measurement: Optional[str] = None,
    ) -> None:
        """Initialize Sonarr sensor."""
        self._available = False
        self._unit_of_measurement = unit_of_measurement
        self._key = key

        super().__init__(
            entry_id=entry_id,
            sonarr=sonarr,
            name=name,
            icon=icon,
            enabled_default=enabled_default,
        )

    def old_init(self, hass, sonarr, conf, sensor_type):
        """Create Sonarr entity."""
        self.conf = conf
        self.included = conf.get(CONF_INCLUDED)
        self.days = int(conf.get(CONF_DAYS))
        self.ssl = "https" if conf.get(CONF_SSL) else "http"
        self._state = None
        self.data = []
        self.type = sensor_type
        self._name = SENSOR_TYPES[self.type][0]
        if self.type == "diskspace":
            self._unit = conf.get(CONF_UNIT)
        else:
            self._unit = SENSOR_TYPES[self.type][1]
        self._icon = SENSOR_TYPES[self.type][2]
        self._available = False

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return f"{self.sonarr.app.info.uuid}_{self._key}"

    @property
    def state(self):
        """Return sensor state."""
        return self._state

    @property
    def available(self):
        """Return sensor availability."""
        return self._available

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        attributes = {}
        if self.type == "upcoming":
            for show in self.data:
                if show["series"]["title"] in attributes:
                    continue

                attributes[show["series"]["title"]] = "S{:02d}E{:02d}".format(
                    show["seasonNumber"], show["episodeNumber"]
                )
        elif self.type == "queue":
            for show in self.data:
                remaining = 1 if show["size"] == 0 else show["sizeleft"] / show["size"]
                attributes[
                    show["series"]["title"]
                    + " S{:02d}E{:02d}".format(
                        show["episode"]["seasonNumber"],
                        show["episode"]["episodeNumber"],
                    )
                ] = "{:.2f}%".format(100 * (1 - (remaining)))
        elif self.type == "wanted":
            for show in self.data:
                attributes[
                    show["series"]["title"]
                    + " S{:02d}E{:02d}".format(
                        show["seasonNumber"], show["episodeNumber"]
                    )
                ] = show["airDate"]
        elif self.type == "commands":
            for command in self.data:
                attributes[command["name"]] = command["state"]
        elif self.type == "diskspace":
            for data in self.data:
                attributes[data["path"]] = "{:.2f}/{:.2f}{} ({:.2f}%)".format(
                    to_unit(data["freeSpace"], self._unit),
                    to_unit(data["totalSpace"], self._unit),
                    self._unit,
                    (
                        to_unit(data["freeSpace"], self._unit)
                        / to_unit(data["totalSpace"], self._unit)
                        * 100
                    ),
                )
        elif self.type == "series":
            for show in self.data:
                if "episodeFileCount" not in show or "episodeCount" not in show:
                    attributes[show["title"]] = "N/A"
                else:
                    attributes[show["title"]] = "{}/{} Episodes".format(
                        show["episodeFileCount"], show["episodeCount"]
                    )
        elif self.type == "status":
            attributes = self.data
        return attributes

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    def old_update(self):
        """Update the data for the sensor."""
        local = dt_util.start_of_local_day().replace(microsecond=0)
        start = dt_util.as_utc(local)
        end = start + timedelta(days=self.days)
        try:
            res = requests.get(
                ENDPOINTS[self.type].format(
                    self.ssl,
                    self.host,
                    self.port,
                    self.urlbase,
                    start.isoformat().replace("+00:00", "Z"),
                    end.isoformat().replace("+00:00", "Z"),
                ),
                headers={"X-Api-Key": self.apikey},
                timeout=10,
            )
        except OSError:
            _LOGGER.warning("Host %s is not available", self.host)
            self._available = False
            self._state = None
            return

        if res.status_code == HTTP_OK:
            if self.type in ["upcoming", "queue", "series", "commands"]:
                self.data = res.json()
                self._state = len(self.data)
            elif self.type == "wanted":
                data = res.json()
                res = requests.get(
                    "{}?pageSize={}".format(
                        ENDPOINTS[self.type].format(
                            self.ssl, self.host, self.port, self.urlbase
                        ),
                        data["totalRecords"],
                    ),
                    headers={"X-Api-Key": self.apikey},
                    timeout=10,
                )
                self.data = res.json()["records"]
                self._state = len(self.data)
            elif self.type == "status":
                self.data = res.json()
                self._state = self.data["version"]
            self._available = True


class SonarrCommandsSensor(SonarrSensor):
    """Defines a Sonarr Commands sensor."""

    def __init__(self, entry_id: str, sonarr: Sonarr) -> None:
        """Initialize Sonarr Commands sensor."""
        self._commands = []

        super().__init__(
            sonarr=sonarr,
            entry_id=entry_id,
            icon="mdi:code-braces",
            key="commands",
            name=f"{sonarr.app.info.app_name} Commands",
            unit_of_measurement=DATA_GIGABYTES,
        )

    def _to_unit(self, value):
        """Return a value converted to unit of measurement."""
        unit = self._unit_of_measurement
        return value / 1024 ** BYTE_SIZES.index(unit)

    async def async_update(self) -> None:
        """Update entity."""
        try:
            commands = await self.sonarr.commands()
            self._available = True
            self._commands = commands
        except SonarrError:
            _LOGGER.exception("Error Updating Sonarr Data")
            self._available = False

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the entity."""
        attrs = {}

        for disk in self._disks:
            free = self._to_unit(disk.free)
            total = self._to_unit(disk.total)

            attrs[disk.path] = "{:.2f}/{:.2f}{} ({:.2f}%)".format(
                free,
                total,
                self._unit_of_measurement,
                (free / total * 100),
            )

        return attrs

    @property
    def state(self) -> Union[None, str, int, float]:
        """Return the state of the sensor."""
        diskspace = sum([disk.free for disk in self._disks])
        return "{:.2f}".format(self._to_unit(diskspace))


class SonarrDiskspaceSensor(SonarrSensor):
    """Defines a Sonarr Disk Space sensor."""

    def __init__(self, entry_id: str, sonarr: Sonarr) -> None:
        """Initialize Sonarr Disk Space sensor."""
        self._disks = []

        super().__init__(
            sonarr=sonarr,
            entry_id=entry_id,
            icon="mdi:harddisk",
            key="diskspace",
            name=f"{sonarr.app.info.app_name} Disk Space",
            unit_of_measurement=DATA_GIGABYTES,
        )

    def _to_unit(self, value):
        """Return a value converted to unit of measurement."""
        unit = self._unit_of_measurement
        return value / 1024 ** BYTE_SIZES.index(unit)

    async def async_update(self) -> None:
        """Update entity."""
        try:
            app = await self.sonarr.update()
            self._available = True
            self._disks = app.disks
        except SonarrError:
            _LOGGER.exception("Error Updating Sonarr Data")
            self._available = False

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the entity."""
        attrs = {}

        for disk in self._disks:
            free = self._to_unit(disk.free)
            total = self._to_unit(disk.total)

            attrs[disk.path] = "{:.2f}/{:.2f}{} ({:.2f}%)".format(
                free,
                total,
                self._unit_of_measurement,
                (free / total * 100),
            )

        return attrs

    @property
    def state(self) -> Union[None, str, int, float]:
        """Return the state of the sensor."""
        diskspace = sum([disk.free for disk in self._disks])
        return "{:.2f}".format(self._to_unit(diskspace))


def get_date(zone, offset=0):
    """Get date based on timezone and offset of days."""
    day = 60 * 60 * 24
    return datetime.date(datetime.fromtimestamp(time.time() + day * offset, tz=zone))
