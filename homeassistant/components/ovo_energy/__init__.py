"""Support for OVO Energy."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

import aiohttp
from ovoenergy import OVOEnergy
from ovoenergy.models import OVODailyUsage

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_ACCOUNT, DATA_CLIENT, DATA_COORDINATOR, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OVO Energy from a config entry."""

    client = OVOEnergy(
        client_session=async_get_clientsession(hass),
    )

    if custom_account := entry.data.get(CONF_ACCOUNT) is not None:
        client.custom_account_id = custom_account

    try:
        if not await client.authenticate(
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
        ):
            raise ConfigEntryAuthFailed

        await client.bootstrap_accounts()
    except aiohttp.ClientError as exception:
        _LOGGER.warning(exception)
        raise ConfigEntryNotReady from exception

    async def async_update_data() -> OVODailyUsage:
        """Fetch data from OVO Energy."""
        if custom_account := entry.data.get(CONF_ACCOUNT) is not None:
            client.custom_account_id = custom_account

        async with asyncio.timeout(10):
            try:
                authenticated = await client.authenticate(
                    entry.data[CONF_USERNAME],
                    entry.data[CONF_PASSWORD],
                )
            except aiohttp.ClientError as exception:
                raise UpdateFailed(exception) from exception
            if not authenticated:
                raise ConfigEntryAuthFailed("Not authenticated with OVO Energy")
            return await client.get_daily_usage(dt_util.utcnow().strftime("%Y-%m"))

    coordinator = DataUpdateCoordinator[OVODailyUsage](
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="sensor",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=3600),
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_CLIENT: client,
        DATA_COORDINATOR: coordinator,
    }

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    # Setup components
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload OVO Energy config entry."""
    # Unload sensors
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    del hass.data[DOMAIN][entry.entry_id]

    return unload_ok
