"""The Poolstation integration."""
from datetime import timedelta
import logging

import aiohttp
from pypoolstation import Account, Pool

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import COORDINATORS, DEVICES, DOMAIN, TOKEN

PLATFORMS = ["sensor"]

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Poolstation from a config entry."""
    session = async_create_clientsession(hass, cookie_jar=aiohttp.DummyCookieJar)
    account = Account(session, token=entry.data[TOKEN])

    try:
        pools = await Pool.get_all_pools(session, account=account)
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        COORDINATORS: {},
        DEVICES: {},
    }

    for pool in pools:
        pool_id = pool.id
        coordinator = PoolstationDataUpdateCoordinator(hass, pool)
        await coordinator.async_config_entry_first_refresh()

        hass.data[DOMAIN][entry.entry_id][DEVICES][pool_id] = pool
        hass.data[DOMAIN][entry.entry_id][COORDINATORS][pool_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class PoolstationDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Poolstation device info."""

    def __init__(self, hass: HomeAssistant, pool: Pool) -> None:
        """Initialize global Poolstation data updater."""
        self._device = pool
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{pool.alias}",
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> None:
        """Fetch data from poolstation.net."""
        await self._device.sync_info()
