"""Support for Sonarr sensors."""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from datetime import timedelta
from functools import wraps
import logging
from typing import Any, TypeVar

from aiopyarr import ArrConnectionException, ArrException, SystemStatus
from aiopyarr.models.host_configuration import PyArrHostConfiguration
from aiopyarr.sonarr_client import SonarrClient
from typing_extensions import Concatenate, ParamSpec

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_GIGABYTES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
import homeassistant.util.dt as dt_util

from .const import (
    CONF_UPCOMING_DAYS,
    CONF_WANTED_MAX_ITEMS,
    DATA_HOST_CONFIG,
    DATA_SONARR,
    DATA_SYSTEM_STATUS,
    DOMAIN,
)
from .entity import SonarrEntity

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="commands",
        name="Sonarr Commands",
        icon="mdi:code-braces",
        native_unit_of_measurement="Commands",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="diskspace",
        name="Sonarr Disk Space",
        icon="mdi:harddisk",
        native_unit_of_measurement=DATA_GIGABYTES,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="queue",
        name="Sonarr Queue",
        icon="mdi:download",
        native_unit_of_measurement="Episodes",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="series",
        name="Sonarr Shows",
        icon="mdi:television",
        native_unit_of_measurement="Series",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="upcoming",
        name="Sonarr Upcoming",
        icon="mdi:television",
        native_unit_of_measurement="Episodes",
    ),
    SensorEntityDescription(
        key="wanted",
        name="Sonarr Wanted",
        icon="mdi:television",
        native_unit_of_measurement="Episodes",
        entity_registry_enabled_default=False,
    ),
)

_SonarrSensorT = TypeVar("_SonarrSensorT", bound="SonarrSensor")
_P = ParamSpec("_P")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sonarr sensors based on a config entry."""
    sonarr: SonarrClient = hass.data[DOMAIN][entry.entry_id][DATA_SONARR]
    host_config: PyArrHostConfiguration = hass.data[DOMAIN][entry.entry_id][
        DATA_HOST_CONFIG
    ]
    system_status: SystemStatus = hass.data[DOMAIN][entry.entry_id][DATA_SYSTEM_STATUS]
    options: dict[str, Any] = dict(entry.options)

    entities = [
        SonarrSensor(
            sonarr,
            host_config,
            system_status,
            entry.entry_id,
            description,
            options,
        )
        for description in SENSOR_TYPES
    ]

    async_add_entities(entities, True)


def sonarr_exception_handler(
    func: Callable[Concatenate[_SonarrSensorT, _P], Awaitable[None]]
) -> Callable[Concatenate[_SonarrSensorT, _P], Coroutine[Any, Any, None]]:
    """Decorate Sonarr calls to handle Sonarr exceptions.

    A decorator that wraps the passed in function, catches Sonarr errors,
    and handles the availability of the entity.
    """

    @wraps(func)
    async def wrapper(
        self: _SonarrSensorT, *args: _P.args, **kwargs: _P.kwargs
    ) -> None:
        try:
            await func(self, *args, **kwargs)
            self.last_update_success = True
        except ArrConnectionException as error:
            if self.last_update_success:
                _LOGGER.error("Error communicating with API: %s", error)
            self.last_update_success = False
        except ArrException as error:
            if self.last_update_success:
                _LOGGER.error("Invalid response from API: %s", error)
                self.last_update_success = False

    return wrapper


class SonarrSensor(SonarrEntity, SensorEntity):
    """Implementation of the Sonarr sensor."""

    data: dict[str, Any]
    last_update_success: bool
    upcoming_days: int
    wanted_max_items: int

    def __init__(
        self,
        sonarr: SonarrClient,
        host_config: PyArrHostConfiguration,
        system_status: SystemStatus,
        entry_id: str,
        description: SensorEntityDescription,
        options: dict[str, Any],
    ) -> None:
        """Initialize Sonarr sensor."""
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"

        self.data = {}
        self.last_update_success = True
        self.upcoming_days = options[CONF_UPCOMING_DAYS]
        self.wanted_max_items = options[CONF_WANTED_MAX_ITEMS]

        super().__init__(
            sonarr=sonarr,
            host_config=host_config,
            system_status=system_status,
            entry_id=entry_id,
            device_id=entry_id,
        )

    @property
    def available(self) -> bool:
        """Return sensor availability."""
        return self.last_update_success

    @sonarr_exception_handler
    async def async_update(self) -> None:
        """Update entity."""
        key = self.entity_description.key

        if key == "diskspace":
            self.data[key] = await self.sonarr.async_get_diskspace()
        elif key == "commands":
            self.data[key] = await self.sonarr.async_get_commands()
        elif key == "queue":
            self.data[key] = await self.sonarr.async_get_queue(
                include_series=True, include_episode=True
            )
        elif key == "series":
            self.data[key] = await self.sonarr.async_get_series()
        elif key == "upcoming":
            local = dt_util.start_of_local_day().replace(microsecond=0)
            start = dt_util.as_utc(local)
            end = start + timedelta(days=self.upcoming_days)

            self.data[key] = await self.sonarr.async_get_calendar(
                start_date=start,
                end_date=end,
                include_series=True,
            )
        elif key == "wanted":
            self.data[key] = await self.sonarr.async_get_wanted(
                page_size=self.wanted_max_items,
                include_series=True,
            )

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the state attributes of the entity."""
        attrs = {}
        key = self.entity_description.key

        if key == "diskspace" and self.data.get(key) is not None:
            for disk in self.data[key]:
                free = disk.freeSpace / 1024**3
                total = disk.totalSpace / 1024**3
                usage = free / total * 100

                attrs[
                    disk.path
                ] = f"{free:.2f}/{total:.2f}{self.unit_of_measurement} ({usage:.2f}%)"
        elif key == "commands" and self.data.get(key) is not None:
            for command in self.data[key]:
                attrs[command.name] = command.status
        elif key == "queue" and self.data.get(key) is not None:
            for item in self.data[key].records:
                remaining = 1 if item.size == 0 else item.sizeleft / item.size
                remaining_pct = 100 * (1 - remaining)
                identifier = f"S{item.episode.seasonNumber:02d}E{item.episode. episodeNumber:02d}"

                name = f"{item.series.title} {identifier}"
                attrs[name] = f"{remaining_pct:.2f}%"
        elif key == "series" and self.data.get(key) is not None:
            for item in self.data[key]:
                stats = item.statistics
                attrs[
                    item.title
                ] = f"{getattr(stats,'episodeFileCount', 0)}/{getattr(stats, 'episodeCount', 0)} Episodes"
        elif key == "upcoming" and self.data.get(key) is not None:
            for episode in self.data[key]:
                identifier = f"S{episode.seasonNumber:02d}E{episode.episodeNumber:02d}"
                attrs[episode.series.title] = identifier
        elif key == "wanted" and self.data.get(key) is not None:
            for item in self.data[key].records:
                identifier = f"S{item.seasonNumber:02d}E{item.episodeNumber:02d}"

                name = f"{item.series.title} {identifier}"
                attrs[name] = dt_util.as_local(
                    item.airDateUtc.replace(tzinfo=dt_util.UTC)
                ).isoformat()

        return attrs

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        key = self.entity_description.key

        if key == "diskspace" and self.data.get(key) is not None:
            total_free = sum(disk.freeSpace for disk in self.data[key])
            free = total_free / 1024**3
            return f"{free:.2f}"

        if key == "commands" and self.data.get(key) is not None:
            return len(self.data[key])

        if key == "queue" and self.data.get(key) is not None:
            return self.data[key].totalRecords

        if key == "series" and self.data.get(key) is not None:
            return len(self.data[key])

        if key == "upcoming" and self.data.get(key) is not None:
            return len(self.data[key])

        if key == "wanted" and self.data.get(key) is not None:
            return self.data[key].totalRecords

        return None
