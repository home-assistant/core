"""The Rituals Perfume Genie integration."""
import asyncio

import aiohttp
from pyrituals import Account

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ACCOUNT_HASH, DOMAIN
from .coordinator import RitualsDataUpdateCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Rituals Perfume Genie from a config entry."""
    session = async_get_clientsession(hass)
    account = Account(session=session, account_hash=entry.data[ACCOUNT_HASH])

    try:
        account_devices = await account.get_devices()
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady from err

    # Create a coordinator for each diffuser
    coordinators = {
        diffuser.hublot: RitualsDataUpdateCoordinator(hass, diffuser)
        for diffuser in account_devices
    }

    # Refresh all coordinators
    await asyncio.gather(
        *[
            coordinator.async_config_entry_first_refresh()
            for coordinator in coordinators.values()
        ]
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
