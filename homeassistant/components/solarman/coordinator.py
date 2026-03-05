"""Coordinator for solarman integration."""

from __future__ import annotations

import logging
from typing import Any

from solarman_opendata.solarman import Solarman

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type SolarmanConfigEntry = ConfigEntry[SolarmanDeviceUpdateCoordinator]


class SolarmanDeviceUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator for managing Solarman device data updates and control operations."""

    config_entry: SolarmanConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: SolarmanConfigEntry, client: Solarman
    ) -> None:
        """Initialize the Solarman device coordinator."""

        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

        # Initialize the API client for communicating with the Solarman device.
        self.api = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch and update device data."""
        data: dict[str, Any] = {}
        try:
            data = await self.api.fetch_data()
        except ConnectionError as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from e

        return data
