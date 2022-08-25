"""The Whirlpool Sixth Sense integration."""
from dataclasses import dataclass
import logging

import aiohttp
from whirlpool.appliancesmanager import AppliancesManager
from whirlpool.auth import Auth
from whirlpool.backendselector import BackendSelector, Brand

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_REGIONS_MAP, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Whirlpool Sixth Sense from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    region = entry.data.get(CONF_REGION, "EU")
    brand = Brand.Whirlpool
    if region == "US":
        brand = Brand.Maytag
    backend_selector = BackendSelector(brand, CONF_REGIONS_MAP[region])
    auth = Auth(backend_selector, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    try:
        await auth.do_auth(store=False)
    except aiohttp.ClientError as ex:
        raise ConfigEntryNotReady("Cannot connect") from ex

    if not auth.is_access_token_valid():
        _LOGGER.error("Authentication failed")
        return False

    appliances_manager = AppliancesManager(backend_selector, auth)
    if not await appliances_manager.fetch_appliances():
        _LOGGER.error("Cannot fetch appliances")
        return False

    hass.data[DOMAIN][entry.entry_id] = WhirlpoolData(
        appliances_manager,
        auth,
        backend_selector,
    )

    myplatform = []

    if appliances_manager.washer_dryers:
        myplatform.append(Platform.SENSOR)

    if appliances_manager.aircons:
        myplatform.append(Platform.CLIMATE)

    if myplatform:
        await hass.config_entries.async_forward_entry_setups(entry, myplatform)

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
