"""Support for Sonarr sensors."""
from datetime import timedelta
import logging
from typing import Any, Callable, Dict, List, Optional, Union

from sonarr import Sonarr, SonarrConnectionError, SonarrError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
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
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
import homeassistant.util.dt as dt_util

from . import SonarrEntity
from .const import (
    CONF_BASE_PATH,
    CONF_DAYS,
    CONF_INCLUDED,
    CONF_UNIT,
    CONF_UPCOMING_DAYS,
    CONF_URLBASE,
    CONF_WANTED_MAX_ITEMS,
    DATA_SONARR,
    DEFAULT_BASE_PATH,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

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

DEFAULT_URLBASE = ""
DEFAULT_DAYS = "1"
DEFAULT_UNIT = DATA_GIGABYTES

PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_INCLUDED, invalidation_version="0.112"),
    cv.deprecated(CONF_MONITORED_CONDITIONS, invalidation_version="0.112"),
    cv.deprecated(CONF_UNIT, invalidation_version="0.112"),
    PLATFORM_SCHEMA.extend(
        {
            vol.Required(CONF_API_KEY): cv.string,
            vol.Optional(CONF_DAYS, default=DEFAULT_DAYS): cv.string,
            vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
            vol.Optional(CONF_INCLUDED, default=[]): cv.ensure_list,
            vol.Optional(CONF_MONITORED_CONDITIONS, default=[]): cv.ensure_list,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
            vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
            vol.Optional(CONF_UNIT, default=DEFAULT_UNIT): vol.In(BYTE_SIZES),
            vol.Optional(CONF_URLBASE, default=DEFAULT_URLBASE): cv.string,
        }
    ),
)


async def async_setup_platform(
    hass: HomeAssistantType,
    config: ConfigType,
    async_add_entities: Callable[[List[Entity], bool], None],
    discovery_info: Any = None,
) -> None:
    """Import the platform into a config entry."""
    if len(hass.config_entries.async_entries(DOMAIN)) > 0:
        return True

    config[CONF_BASE_PATH] = f"{config[CONF_URLBASE]}{DEFAULT_BASE_PATH}"
    config[CONF_UPCOMING_DAYS] = int(config[CONF_DAYS])
    config[CONF_VERIFY_SSL] = False

    del config[CONF_DAYS]
    del config[CONF_INCLUDED]
    del config[CONF_MONITORED_CONDITIONS]
    del config[CONF_URLBASE]

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up Sonarr sensors based on a config entry."""
    options = entry.options
    sonarr = hass.data[DOMAIN][entry.entry_id][DATA_SONARR]

    entities = [
        SonarrCommandsSensor(sonarr, entry.entry_id),
        SonarrDiskspaceSensor(sonarr, entry.entry_id),
        SonarrQueueSensor(sonarr, entry.entry_id),
        SonarrSeriesSensor(sonarr, entry.entry_id),
        SonarrUpcomingSensor(sonarr, entry.entry_id, days=options[CONF_UPCOMING_DAYS]),
        SonarrWantedSensor(
            sonarr, entry.entry_id, max_items=options[CONF_WANTED_MAX_ITEMS]
        ),
    ]

    async_add_entities(entities, True)


def sonarr_exception_handler(func):
    """Decorate Sonarr calls to handle Sonarr exceptions.

    A decorator that wraps the passed in function, catches Sonarr errors,
    and handles the availability of the entity.
    """

    async def handler(self, *args, **kwargs):
        try:
            await func(self, *args, **kwargs)
            self.last_update_success = True
        except SonarrConnectionError as error:
            if self.available:
                _LOGGER.error("Error communicating with API: %s", error)
            self.last_update_success = False
        except SonarrError as error:
            if self.available:
                _LOGGER.error("Invalid response from API: %s", error)
                self.last_update_success = False

    return handler


class SonarrSensor(SonarrEntity):
    """Implementation of the Sonarr sensor."""

    def __init__(
        self,
        *,
        sonarr: Sonarr,
        entry_id: str,
        enabled_default: bool = True,
        icon: str,
        key: str,
        name: str,
        unit_of_measurement: Optional[str] = None,
    ) -> None:
        """Initialize Sonarr sensor."""
        self._unit_of_measurement = unit_of_measurement
        self._key = key
        self._unique_id = f"{entry_id}_{key}"
        self.last_update_success = False

        super().__init__(
            sonarr=sonarr,
            entry_id=entry_id,
            device_id=entry_id,
            name=name,
            icon=icon,
            enabled_default=enabled_default,
        )

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return self._unique_id

    @property
    def available(self) -> bool:
        """Return sensor availability."""
        return self.last_update_success

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement


class SonarrCommandsSensor(SonarrSensor):
    """Defines a Sonarr Commands sensor."""

    def __init__(self, sonarr: Sonarr, entry_id: str) -> None:
        """Initialize Sonarr Commands sensor."""
        self._commands = []

        super().__init__(
            sonarr=sonarr,
            entry_id=entry_id,
            icon="mdi:code-braces",
            key="commands",
            name=f"{sonarr.app.info.app_name} Commands",
            unit_of_measurement="Commands",
            enabled_default=False,
        )

    @sonarr_exception_handler
    async def async_update(self) -> None:
        """Update entity."""
        self._commands = await self.sonarr.commands()

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the entity."""
        attrs = {}

        for command in self._commands:
            attrs[command.name] = command.state

        return attrs

    @property
    def state(self) -> Union[None, str, int, float]:
        """Return the state of the sensor."""
        return len(self._commands)


class SonarrDiskspaceSensor(SonarrSensor):
    """Defines a Sonarr Disk Space sensor."""

    def __init__(self, sonarr: Sonarr, entry_id: str) -> None:
        """Initialize Sonarr Disk Space sensor."""
        self._disks = []
        self._total_free = 0

        super().__init__(
            sonarr=sonarr,
            entry_id=entry_id,
            icon="mdi:harddisk",
            key="diskspace",
            name=f"{sonarr.app.info.app_name} Disk Space",
            unit_of_measurement=DATA_GIGABYTES,
            enabled_default=False,
        )

    def _to_unit(self, value):
        """Return a value converted to unit of measurement."""
        return value / 1024 ** BYTE_SIZES.index(self._unit_of_measurement)

    @sonarr_exception_handler
    async def async_update(self) -> None:
        """Update entity."""
        app = await self.sonarr.update()
        self._disks = app.disks
        self._total_free = sum([disk.free for disk in self._disks])

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the entity."""
        attrs = {}

        for disk in self._disks:
            free = self._to_unit(disk.free)
            total = self._to_unit(disk.total)
            usage = free / total * 100

            attrs[
                disk.path
            ] = f"{free:.2f}/{total:.2f}{self._unit_of_measurement} ({usage:.2f}%)"

        return attrs

    @property
    def state(self) -> Union[None, str, int, float]:
        """Return the state of the sensor."""
        free = self._to_unit(self._total_free)
        return f"{free:.2f}"


class SonarrQueueSensor(SonarrSensor):
    """Defines a Sonarr Queue sensor."""

    def __init__(self, sonarr: Sonarr, entry_id: str) -> None:
        """Initialize Sonarr Queue sensor."""
        self._queue = []

        super().__init__(
            sonarr=sonarr,
            entry_id=entry_id,
            icon="mdi:download",
            key="queue",
            name=f"{sonarr.app.info.app_name} Queue",
            unit_of_measurement="Episodes",
            enabled_default=False,
        )

    @sonarr_exception_handler
    async def async_update(self) -> None:
        """Update entity."""
        self._queue = await self.sonarr.queue()

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the entity."""
        attrs = {}

        for item in self._queue:
            remaining = 1 if item.size == 0 else item.size_remaining / item.size
            remaining_pct = 100 * (1 - remaining)
            name = f"{item.episode.series.title} {item.episode.identifier}"
            attrs[name] = f"{remaining_pct:.2f}%"

        return attrs

    @property
    def state(self) -> Union[None, str, int, float]:
        """Return the state of the sensor."""
        return len(self._queue)


class SonarrSeriesSensor(SonarrSensor):
    """Defines a Sonarr Series sensor."""

    def __init__(self, sonarr: Sonarr, entry_id: str) -> None:
        """Initialize Sonarr Series sensor."""
        self._items = []

        super().__init__(
            sonarr=sonarr,
            entry_id=entry_id,
            icon="mdi:television",
            key="series",
            name=f"{sonarr.app.info.app_name} Shows",
            unit_of_measurement="Series",
            enabled_default=False,
        )

    @sonarr_exception_handler
    async def async_update(self) -> None:
        """Update entity."""
        self._items = await self.sonarr.series()

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the entity."""
        attrs = {}

        for item in self._items:
            attrs[item.series.title] = f"{item.downloaded}/{item.episodes} Episodes"

        return attrs

    @property
    def state(self) -> Union[None, str, int, float]:
        """Return the state of the sensor."""
        return len(self._items)


class SonarrUpcomingSensor(SonarrSensor):
    """Defines a Sonarr Upcoming sensor."""

    def __init__(self, sonarr: Sonarr, entry_id: str, days: int = 1) -> None:
        """Initialize Sonarr Upcoming sensor."""
        self._days = days
        self._upcoming = []

        super().__init__(
            sonarr=sonarr,
            entry_id=entry_id,
            icon="mdi:television",
            key="upcoming",
            name=f"{sonarr.app.info.app_name} Upcoming",
            unit_of_measurement="Episodes",
        )

    async def async_added_to_hass(self):
        """Listen for signals."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"sonarr.{self._entry_id}.entry_options_update",
                self.async_update_entry_options,
            )
        )

    @sonarr_exception_handler
    async def async_update(self) -> None:
        """Update entity."""
        local = dt_util.start_of_local_day().replace(microsecond=0)
        start = dt_util.as_utc(local)
        end = start + timedelta(days=self._days)
        self._upcoming = await self.sonarr.calendar(
            start=start.isoformat(), end=end.isoformat()
        )

    async def async_update_entry_options(self, options: dict) -> None:
        """Update sensor settings when config entry options are update."""
        self._days = options[CONF_UPCOMING_DAYS]

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the entity."""
        attrs = {}

        for episode in self._upcoming:
            attrs[episode.series.title] = episode.identifier

        return attrs

    @property
    def state(self) -> Union[None, str, int, float]:
        """Return the state of the sensor."""
        return len(self._upcoming)


class SonarrWantedSensor(SonarrSensor):
    """Defines a Sonarr Wanted sensor."""

    def __init__(self, sonarr: Sonarr, entry_id: str, max_items: int = 10) -> None:
        """Initialize Sonarr Wanted sensor."""
        self._max_items = max_items
        self._results = None
        self._total = None

        super().__init__(
            sonarr=sonarr,
            entry_id=entry_id,
            icon="mdi:television",
            key="wanted",
            name=f"{sonarr.app.info.app_name} Wanted",
            unit_of_measurement="Episodes",
            enabled_default=False,
        )

    async def async_added_to_hass(self):
        """Listen for signals."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"sonarr.{self._entry_id}.entry_options_update",
                self.async_update_entry_options,
            )
        )

    @sonarr_exception_handler
    async def async_update(self) -> None:
        """Update entity."""
        self._results = await self.sonarr.wanted(page_size=self._max_items)
        self._total = self._results.total

    async def async_update_entry_options(self, options: dict) -> None:
        """Update sensor settings when config entry options are update."""
        self._max_items = options[CONF_WANTED_MAX_ITEMS]

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the entity."""
        attrs = {}

        if self._results is not None:
            for episode in self._results.episodes:
                name = f"{episode.series.title} {episode.identifier}"
                attrs[name] = episode.airdate

        return attrs

    @property
    def state(self) -> Union[None, str, int, float]:
        """Return the state of the sensor."""
        return self._total
