"""The Whirlpool Appliances integration."""

import logging

from aiohttp import ClientError
from whirlpool.appliancesmanager import AppliancesManager
from whirlpool.auth import AccountLockedError as WhirlpoolAccountLocked, Auth
from whirlpool.backendselector import BackendSelector

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import BRANDS_CONF_MAP, CONF_BRAND, DOMAIN, REGIONS_CONF_MAP

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.CLIMATE, Platform.SENSOR]

type WhirlpoolConfigEntry = ConfigEntry[AppliancesManager]


async def async_setup_entry(hass: HomeAssistant, entry: WhirlpoolConfigEntry) -> bool:
    """Set up Whirlpool Sixth Sense from a config entry."""
    session = async_get_clientsession(hass)
    region = REGIONS_CONF_MAP[entry.data.get(CONF_REGION, "EU")]
    brand = BRANDS_CONF_MAP[entry.data.get(CONF_BRAND, "Whirlpool")]
    backend_selector = BackendSelector(brand, region)

    auth = Auth(
        backend_selector, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD], session
    )
    try:
        await auth.do_auth(store=False)
    except (ClientError, TimeoutError) as ex:
        raise ConfigEntryNotReady("Cannot connect") from ex
    except WhirlpoolAccountLocked as ex:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="account_locked"
        ) from ex

    if not auth.is_access_token_valid():
        _LOGGER.error("Authentication failed")
        raise ConfigEntryAuthFailed("Incorrect Password")

    appliances_manager = AppliancesManager(backend_selector, auth, session)
    if not await appliances_manager.fetch_appliances():
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="appliances_fetch_failed"
        )
    await appliances_manager.connect()

    entry.runtime_data = appliances_manager

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WhirlpoolConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.disconnect()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
