"""The Poolstation integration."""
from datetime import timedelta
import logging

import aiohttp
from pypoolstation import Account, AuthenticationException, Pool

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import COORDINATORS, DEVICES, DOMAIN
from .util import create_account

PLATFORMS = ["sensor", "number", "switch"]

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Poolstation from a config entry."""
    session = async_create_clientsession(hass, cookie_jar=aiohttp.DummyCookieJar())
    account = Account(session, token=entry.data[CONF_TOKEN], logger=_LOGGER)

    try:
        pools = await Pool.get_all_pools(session, account=account)
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady from err
    except AuthenticationException as err:
        account = create_account(
            session, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD], _LOGGER
        )
        try:
            token = await account.login()
        except AuthenticationException:
            # Unfortunately the poolstation API is crap and logging with wrong credentials returns a 500 instead of a 401
            # That's why this block is probably never being called. Instead the next except will.
            raise ConfigEntryAuthFailed from err
        except aiohttp.ClientResponseError:
            raise ConfigEntryAuthFailed from err
        else:
            hass.config_entries.async_update_entry(
                entry,
                data={
                    CONF_TOKEN: token,
                    CONF_EMAIL: entry.data[CONF_EMAIL],
                    CONF_PASSWORD: entry.data[CONF_PASSWORD],
                },
            )
            pools = await Pool.get_all_pools(session, account=account)

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
        try:
            await self._device.sync_info()
        except AuthenticationException as err:
            raise ConfigEntryAuthFailed from err
