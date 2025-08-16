"""Data update coordinator for Green Planet Energy."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from greenplanet_energy_api import (
    GreenPlanetEnergyAPI,
    GreenPlanetEnergyAPIError,
    GreenPlanetEnergyConnectionError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class GreenPlanetEnergyUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from Green Planet Energy API."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL),
            config_entry=config_entry,
        )
        self.api = GreenPlanetEnergyAPI(session=async_get_clientsession(hass))

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            return await self.api.get_electricity_prices()
        except GreenPlanetEnergyConnectionError as err:
            raise UpdateFailed(f"Connection error: {err}") from err
        except GreenPlanetEnergyAPIError as err:
            raise UpdateFailed(f"API error: {err}") from err
