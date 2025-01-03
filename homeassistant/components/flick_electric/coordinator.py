"""Data Coordinator for Flick Electric."""

import asyncio
from datetime import timedelta
import logging

import aiohttp
from pyflick import FlickAPI, FlickPrice
from pyflick.types import APIException, AuthException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)

type FlickConfigEntry = ConfigEntry[FlickElectricDataCoordinator]


class FlickElectricDataCoordinator(DataUpdateCoordinator[FlickPrice]):
    """Coordinator for flick power price."""

    def __init__(
        self, hass: HomeAssistant, api: FlickAPI, supply_node_ref: str
    ) -> None:
        """Initialize FlickElectricDataCoordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Flick Electric",
            update_interval=SCAN_INTERVAL,
        )
        self.supply_node_ref = supply_node_ref
        self._api = api

    async def _async_update_data(self) -> FlickPrice:
        """Fetch pricing data from Flick Electric."""
        try:
            async with asyncio.timeout(60):
                return await self._api.getPricing(self.supply_node_ref)
        except AuthException as err:
            raise ConfigEntryAuthFailed from err
        except (APIException, aiohttp.ClientResponseError) as err:
            raise UpdateFailed from err
