"""Provide an OpenExchangeRates data coordinator."""

from __future__ import annotations

import asyncio
from datetime import timedelta

from aiohttp import ClientSession
from aioopenexchangerates import (
    Client,
    Latest,
    OpenExchangeRatesAuthError,
    OpenExchangeRatesClientError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CLIENT_TIMEOUT, DOMAIN, LOGGER


class OpenexchangeratesCoordinator(DataUpdateCoordinator[Latest]):
    """Represent a coordinator for Open Exchange Rates API."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        session: ClientSession,
        api_key: str,
        base: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} base {base}",
            update_interval=update_interval,
        )
        self.base = base
        self.client = Client(api_key, session)

    async def _async_update_data(self) -> Latest:
        """Update data from Open Exchange Rates."""
        try:
            async with asyncio.timeout(CLIENT_TIMEOUT):
                latest = await self.client.get_latest(base=self.base)
        except OpenExchangeRatesAuthError as err:
            raise ConfigEntryAuthFailed(err) from err
        except OpenExchangeRatesClientError as err:
            raise UpdateFailed(err) from err

        LOGGER.debug("Result: %s", latest)
        return latest
