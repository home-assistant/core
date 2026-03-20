"""Coordinator for solarman integration."""

from __future__ import annotations

import logging
from typing import Any

from solarman_opendata.solarman import Solarman

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_PORT, DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type SolarmanConfigEntry = ConfigEntry[SolarmanDeviceUpdateCoordinator]


class SolarmanDeviceUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for managing Solarman device data updates and control operations."""

    config_entry: SolarmanConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: SolarmanConfigEntry) -> None:
        """Initialize the Solarman device coordinator."""

        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

        self.api = Solarman(
            async_get_clientsession(hass), config_entry.data[CONF_HOST], DEFAULT_PORT
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch and update device data."""
        try:
            return await self.api.fetch_data()
        except ConnectionError as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from e
