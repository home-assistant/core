"""The Whirlpool Appliances integration."""
import asyncio
from dataclasses import dataclass
import logging

from aiohttp import ClientError
from whirlpool.appliancesmanager import AppliancesManager
from whirlpool.auth import Auth
from whirlpool.backendselector import BackendSelector

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_REGIONS_MAP, DOMAIN
from .util import get_brand_for_region

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Whirlpool Sixth Sense from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    region = CONF_REGIONS_MAP[entry.data.get(CONF_REGION, "EU")]
    brand = get_brand_for_region(region)
    backend_selector = BackendSelector(brand, region)
    auth = Auth(
        backend_selector, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD], session
    )
    try:
        await auth.do_auth(store=False)
    except (ClientError, asyncio.TimeoutError) as ex:
        raise ConfigEntryNotReady("Cannot connect") from ex

    if not auth.is_access_token_valid():
        _LOGGER.error("Authentication failed")
        raise ConfigEntryAuthFailed("Incorrect Password")

    appliances_manager = AppliancesManager(backend_selector, auth, session)
    if not await appliances_manager.fetch_appliances():
        _LOGGER.error("Cannot fetch appliances")
        return False

    hass.data[DOMAIN][entry.entry_id] = WhirlpoolData(
        appliances_manager, auth, backend_selector
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
