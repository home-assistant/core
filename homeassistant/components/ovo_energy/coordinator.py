"""Coordinator for the OVO Energy integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

import aiohttp
from ovoenergy import OVOEnergy
from ovoenergy.models import OVODailyUsage

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_ACCOUNT

_LOGGER = logging.getLogger(__name__)

type OVOEnergyConfigEntry = ConfigEntry[OVOEnergyDataUpdateCoordinator]


class OVOEnergyDataUpdateCoordinator(DataUpdateCoordinator[OVODailyUsage]):
    """Class to manage fetching OVO Energy data."""

    config_entry: OVOEnergyConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OVOEnergyConfigEntry,
        client: OVOEnergy,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="sensor",
            update_interval=timedelta(seconds=3600),
        )
        self.client = client

    async def _async_update_data(self) -> OVODailyUsage:
        """Fetch data from OVO Energy."""
        if (custom_account := self.config_entry.data.get(CONF_ACCOUNT)) is not None:
            self.client.custom_account_id = custom_account

        async with asyncio.timeout(10):
            try:
                authenticated = await self.client.authenticate(
                    self.config_entry.data[CONF_USERNAME],
                    self.config_entry.data[CONF_PASSWORD],
                )
            except aiohttp.ClientError as exception:
                raise UpdateFailed(exception) from exception
            if not authenticated:
                raise ConfigEntryAuthFailed("Not authenticated with OVO Energy")
            return await self.client.get_daily_usage(dt_util.utcnow().strftime("%Y-%m"))
