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
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

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
        self.session = async_get_clientsession(hass)
        self.api = GreenPlanetEnergyAPI(session=self.session)

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            return await self.api.get_electricity_prices()
        except GreenPlanetEnergyConnectionError as err:
            _LOGGER.warning(
                "Connection error fetching data from Green Planet Energy API: %s", err
            )
            # Return empty data instead of raising an error
            # This prevents the integration from failing completely
            return {}
        except GreenPlanetEnergyAPIError as err:
            _LOGGER.error(
                "API error fetching data from Green Planet Energy API: %s", err
            )
            # Return empty data instead of raising an error
            # This prevents the integration from failing completely
            return {}

    async def async_shutdown(self) -> None:
        """Shutdown coordinator."""
        await super().async_shutdown()
        await self.api.close()
