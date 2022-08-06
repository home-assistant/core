"""Provide an OpenExchangeRates data coordinator."""
from __future__ import annotations

import asyncio
from datetime import timedelta

from aiohttp import ClientSession
from aioopenexchangerates import Client, Latest, OpenExchangeRatesClientError
import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

TIMEOUT = 10


class OpenexchangeratesCoordinator(DataUpdateCoordinator[Latest]):
    """Represent a coordinator for Open Exchange Rates API."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: ClientSession,
        api_key: str,
        base: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass, LOGGER, name=f"{DOMAIN} base {base}", update_interval=update_interval
        )
        self.base = base
        self.client = Client(api_key, session)
        self.setup_lock = asyncio.Lock()

    async def _async_update_data(self) -> Latest:
        """Update data from Open Exchange Rates."""
        try:
            async with async_timeout.timeout(TIMEOUT):
                latest = await self.client.get_latest(base=self.base)
        except (OpenExchangeRatesClientError) as err:
            raise UpdateFailed(err) from err

        LOGGER.debug("Result: %s", latest)
        return latest
