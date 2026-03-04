"""The Mullvad VPN coordinator."""

import asyncio
from datetime import timedelta
import logging
from typing import Any

from mullvad_api import MullvadAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class MullvadCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Mullvad VPN data update coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Mullvad coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=1),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Mullvad API."""
        async with asyncio.timeout(10):
            api = await self.hass.async_add_executor_job(MullvadAPI)
            return api.data
