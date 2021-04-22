"""Support for Sonarr sensors."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, Callable

from sonarr import Sonarr, SonarrConnectionError, SonarrError

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_GIGABYTES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util

from . import SonarrEntity
from .const import CONF_UPCOMING_DAYS, CONF_WANTED_MAX_ITEMS, DATA_SONARR, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[list[Entity], bool], None],
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


class SonarrSensor(SonarrEntity, SensorEntity):
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
        unit_of_measurement: str | None = None,
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
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the entity."""
        attrs = {}

        for command in self._commands:
            attrs[command.name] = command.state

        return attrs

    @property
    def state(self) -> int:
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

    @sonarr_exception_handler
    async def async_update(self) -> None:
        """Update entity."""
        app = await self.sonarr.update()
        self._disks = app.disks
        self._total_free = sum([disk.free for disk in self._disks])

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the entity."""
        attrs = {}

        for disk in self._disks:
            free = disk.free / 1024 ** 3
            total = disk.total / 1024 ** 3
            usage = free / total * 100

            attrs[
                disk.path
            ] = f"{free:.2f}/{total:.2f}{self._unit_of_measurement} ({usage:.2f}%)"

        return attrs

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        free = self._total_free / 1024 ** 3
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
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the entity."""
        attrs = {}

        for item in self._queue:
            remaining = 1 if item.size == 0 else item.size_remaining / item.size
            remaining_pct = 100 * (1 - remaining)
            name = f"{item.episode.series.title} {item.episode.identifier}"
            attrs[name] = f"{remaining_pct:.2f}%"

        return attrs

    @property
    def state(self) -> int:
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
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the entity."""
        attrs = {}

        for item in self._items:
            attrs[item.series.title] = f"{item.downloaded}/{item.episodes} Episodes"

        return attrs

    @property
    def state(self) -> int:
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

    @sonarr_exception_handler
    async def async_update(self) -> None:
        """Update entity."""
        local = dt_util.start_of_local_day().replace(microsecond=0)
        start = dt_util.as_utc(local)
        end = start + timedelta(days=self._days)
        self._upcoming = await self.sonarr.calendar(
            start=start.isoformat(), end=end.isoformat()
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the entity."""
        attrs = {}

        for episode in self._upcoming:
            attrs[episode.series.title] = episode.identifier

        return attrs

    @property
    def state(self) -> int:
        """Return the state of the sensor."""
        return len(self._upcoming)


class SonarrWantedSensor(SonarrSensor):
    """Defines a Sonarr Wanted sensor."""

    def __init__(self, sonarr: Sonarr, entry_id: str, max_items: int = 10) -> None:
        """Initialize Sonarr Wanted sensor."""
        self._max_items = max_items
        self._results = None
        self._total: int | None = None

        super().__init__(
            sonarr=sonarr,
            entry_id=entry_id,
            icon="mdi:television",
            key="wanted",
            name=f"{sonarr.app.info.app_name} Wanted",
            unit_of_measurement="Episodes",
            enabled_default=False,
        )

    @sonarr_exception_handler
    async def async_update(self) -> None:
        """Update entity."""
        self._results = await self.sonarr.wanted(page_size=self._max_items)
        self._total = self._results.total

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the entity."""
        attrs = {}

        if self._results is not None:
            for episode in self._results.episodes:
                name = f"{episode.series.title} {episode.identifier}"
                attrs[name] = episode.airdate

        return attrs

    @property
    def state(self) -> int | None:
        """Return the state of the sensor."""
        return self._total
