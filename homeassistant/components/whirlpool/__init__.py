"""The Whirlpool Sixth Sense integration."""
from dataclasses import dataclass
import logging

import aiohttp
from whirlpool.appliancesmanager import AppliancesManager
from whirlpool.auth import Auth
from whirlpool.backendselector import BackendSelector, Brand, Region

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Whirlpool Sixth Sense from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    backend_selector = BackendSelector(Brand.Whirlpool, Region.EU)
    auth = Auth(backend_selector, entry.data["username"], entry.data["password"])
    try:
        await auth.do_auth(store=False)
    except aiohttp.ClientError as ex:
        raise ConfigEntryNotReady("Cannot connect") from ex

    if not auth.is_access_token_valid():
        _LOGGER.error("Authentication failed")
        raise ConfigEntryAuthFailed("Incorrect Password")

    appliances_manager = AppliancesManager(backend_selector, auth)
    if not await appliances_manager.fetch_appliances():
        _LOGGER.error("Cannot fetch appliances")
        return False

    hass.data[DOMAIN][entry.entry_id] = WhirlpoolData(
        appliances_manager,
        auth,
        backend_selector,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


@dataclass
class WhirlpoolData:
    """Whirlpool integaration shared data."""

    appliances_manager: AppliancesManager
    auth: Auth
    backend_selector: BackendSelector
