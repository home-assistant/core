"""The Ridwell integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta

from aioridwell import async_get_client
from aioridwell.client import RidwellAccount, RidwellPickupEvent
from aioridwell.errors import InvalidCredentialsError, RidwellError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DATA_ACCOUNT, DATA_COORDINATOR, DOMAIN, LOGGER

DEFAULT_UPDATE_INTERVAL = timedelta(hours=1)

PLATFORMS: list[str] = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ridwell from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    session = aiohttp_client.async_get_clientsession(hass)

    try:
        client = await async_get_client(
            entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD], session=session
        )
    except InvalidCredentialsError as err:
        raise ConfigEntryAuthFailed("Invalid username/password") from err
    except RidwellError as err:
        LOGGER.error("Error while authenticating with WattTime: %s", err)
        return False

    accounts = await client.async_get_accounts()

    async def async_update_data() -> dict[str, RidwellPickupEvent]:
        """Get the latest pickup events."""
        data = {}

        async def async_get_pickups(account: RidwellAccount) -> None:
            """Get the latest pickups for an account."""
            data[account.account_id] = await account.async_get_next_pickup_event()

        tasks = [async_get_pickups(account) for account in accounts.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, InvalidCredentialsError):
                raise ConfigEntryAuthFailed("Invalid username/password") from result
            if isinstance(result, RidwellError):
                raise UpdateFailed(result) from result

        return data

    coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=entry.title,
        update_interval=DEFAULT_UPDATE_INTERVAL,
        update_method=async_update_data,
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id][DATA_ACCOUNT] = accounts
    hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
