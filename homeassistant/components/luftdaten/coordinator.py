"""Support for Sensor.Community stations.

Sensor.Community was previously called Luftdaten, hence the domain differs from
the integration name.
"""

from __future__ import annotations

import logging

from luftdaten import Luftdaten
from luftdaten.exceptions import LuftdatenError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type LuftdatenConfigEntry = ConfigEntry[LuftdatenDataUpdateCoordinator]


class LuftdatenDataUpdateCoordinator(DataUpdateCoordinator[dict[str, float | int]]):
    """Data update coordinator for Sensor.Community."""

    config_entry: LuftdatenConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: LuftdatenConfigEntry,
        sensor_community: Luftdaten,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{sensor_community.sensor_id}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self._sensor_community = sensor_community

    async def _async_update_data(self) -> dict[str, float | int]:
        """Update sensor/binary sensor data."""
        try:
            await self._sensor_community.get_data()
        except LuftdatenError as err:
            raise UpdateFailed("Unable to retrieve data from Sensor.Community") from err

        if not self._sensor_community.values:
            raise UpdateFailed("Did not receive sensor data from Sensor.Community")

        data: dict[str, float | int] = self._sensor_community.values
        data.update(self._sensor_community.meta)
        return data
