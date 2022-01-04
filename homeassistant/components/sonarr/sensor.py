"""Support for Sonarr sensors."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from sonarr import Sonarr, SonarrConnectionError, SonarrError

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_GIGABYTES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
import homeassistant.util.dt as dt_util

from .const import CONF_UPCOMING_DAYS, CONF_WANTED_MAX_ITEMS, DATA_SONARR, DOMAIN
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sonarr sensors based on a config entry."""
    sonarr: Sonarr = hass.data[DOMAIN][entry.entry_id][DATA_SONARR]
    options: dict[str, Any] = dict(entry.options)

    entities = [
        SonarrSensor(sonarr, entry.entry_id, description, options)
        for description in SENSOR_TYPES
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
        sonarr: Sonarr,
        entry_id: str,
        description: SensorEntityDescription,
        options: dict[str, Any],
    ) -> None:
        """Initialize Sonarr sensor."""
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"

        self.data: dict[str, Any] = {}
        self.last_update_success: bool = False
        self.upcoming_days: int = options[CONF_UPCOMING_DAYS]
        self.wanted_max_items: int = options[CONF_WANTED_MAX_ITEMS]

        super().__init__(
            sonarr=sonarr,
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
            await self.sonarr.update()
        elif key == "commands":
            self.data[key] = await self.sonarr.commands()
        elif key == "queue":
            self.data[key] = await self.sonarr.queue()
        elif key == "series":
            self.data[key] = await self.sonarr.series()
        elif key == "upcoming":
            local = dt_util.start_of_local_day().replace(microsecond=0)
            start = dt_util.as_utc(local)
            end = start + timedelta(days=self.upcoming_days)

            self.data[key] = await self.sonarr.calendar(
                start=start.isoformat(), end=end.isoformat()
            )
        elif key == "wanted":
            self.data[key] = await self.sonarr.wanted(page_size=self.wanted_max_items)

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the state attributes of the entity."""
        attrs = {}
        key = self.entity_description.key

        if key == "diskspace":
            for disk in self.sonarr.app.disks:
                free = disk.free / 1024 ** 3
                total = disk.total / 1024 ** 3
                usage = free / total * 100

                attrs[
                    disk.path
                ] = f"{free:.2f}/{total:.2f}{self.unit_of_measurement} ({usage:.2f}%)"
        elif key == "commands" and self.data.get(key) is not None:
            for command in self.data[key]:
                attrs[command.name] = command.state
        elif key == "queue" and self.data.get(key) is not None:
            for item in self.data[key]:
                remaining = 1 if item.size == 0 else item.size_remaining / item.size
                remaining_pct = 100 * (1 - remaining)
                name = f"{item.episode.series.title} {item.episode.identifier}"
                attrs[name] = f"{remaining_pct:.2f}%"
        elif key == "series" and self.data.get(key) is not None:
            for item in self.data[key]:
                attrs[item.series.title] = f"{item.downloaded}/{item.episodes} Episodes"
        elif key == "upcoming" and self.data.get(key) is not None:
            for episode in self.data[key]:
                attrs[episode.series.title] = episode.identifier
        elif key == "wanted" and self.data.get(key) is not None:
            for episode in self.data[key].episodes:
                name = f"{episode.series.title} {episode.identifier}"
                attrs[name] = episode.airdate

        return attrs

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        key = self.entity_description.key

        if key == "diskspace":
            total_free = sum(disk.free for disk in self.sonarr.app.disks)
            free = total_free / 1024 ** 3
            return f"{free:.2f}"

        if key == "commands" and self.data.get(key) is not None:
            return len(self.data[key])

        if key == "queue" and self.data.get(key) is not None:
            return len(self.data[key])

        if key == "series" and self.data.get(key) is not None:
            return len(self.data[key])

        if key == "upcoming" and self.data.get(key) is not None:
            return len(self.data[key])

        if key == "wanted" and self.data.get(key) is not None:
            return self.data[key].total

        return None
