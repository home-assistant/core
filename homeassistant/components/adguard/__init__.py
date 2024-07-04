"""Support for AdGuard Home."""

from __future__ import annotations

from dataclasses import dataclass

from adguardhome import AdGuardHome, AdGuardHomeConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_FORCE,
    DOMAIN,
    SERVICE_ADD_URL,
    SERVICE_DISABLE_URL,
    SERVICE_ENABLE_URL,
    SERVICE_REFRESH,
    SERVICE_REMOVE_URL,
)

SERVICE_URL_SCHEMA = vol.Schema({vol.Required(CONF_URL): cv.url})
SERVICE_ADD_URL_SCHEMA = vol.Schema(
    {vol.Required(CONF_NAME): cv.string, vol.Required(CONF_URL): cv.url}
)
SERVICE_REFRESH_SCHEMA = vol.Schema(
    {vol.Optional(CONF_FORCE, default=False): cv.boolean}
)

PLATFORMS = [Platform.SENSOR, Platform.SWITCH]
type AdGuardConfigEntry = ConfigEntry[AdGuardData]


@dataclass
class AdGuardData:
    """Adguard data type."""

    client: AdGuardHome
    version: str


async def async_setup_entry(hass: HomeAssistant, entry: AdGuardConfigEntry) -> bool:
    """Set up AdGuard Home from a config entry."""
    session = async_get_clientsession(hass, entry.data[CONF_VERIFY_SSL])
    adguard = AdGuardHome(
        entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        tls=entry.data[CONF_SSL],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
        session=session,
    )

    try:
        version = await adguard.version()
    except AdGuardHomeConnectionError as exception:
        raise ConfigEntryNotReady from exception

    entry.runtime_data = AdGuardData(adguard, version)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def add_url(call: ServiceCall) -> None:
        """Service call to add a new filter subscription to AdGuard Home."""
        await adguard.filtering.add_url(
            allowlist=False, name=call.data[CONF_NAME], url=call.data[CONF_URL]
        )

    async def remove_url(call: ServiceCall) -> None:
        """Service call to remove a filter subscription from AdGuard Home."""
        await adguard.filtering.remove_url(allowlist=False, url=call.data[CONF_URL])

    async def enable_url(call: ServiceCall) -> None:
        """Service call to enable a filter subscription in AdGuard Home."""
        await adguard.filtering.enable_url(allowlist=False, url=call.data[CONF_URL])

    async def disable_url(call: ServiceCall) -> None:
        """Service call to disable a filter subscription in AdGuard Home."""
        await adguard.filtering.disable_url(allowlist=False, url=call.data[CONF_URL])

    async def refresh(call: ServiceCall) -> None:
        """Service call to refresh the filter subscriptions in AdGuard Home."""
        await adguard.filtering.refresh(allowlist=False, force=call.data[CONF_FORCE])

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_URL, add_url, schema=SERVICE_ADD_URL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE_URL, remove_url, schema=SERVICE_URL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ENABLE_URL, enable_url, schema=SERVICE_URL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DISABLE_URL, disable_url, schema=SERVICE_URL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REFRESH, refresh, schema=SERVICE_REFRESH_SCHEMA
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AdGuardConfigEntry) -> bool:
    """Unload AdGuard Home config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    loaded_entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state == ConfigEntryState.LOADED
    ]
    if len(loaded_entries) == 1:
        # This is the last loaded instance of AdGuard, deregister any services
        hass.services.async_remove(DOMAIN, SERVICE_ADD_URL)
        hass.services.async_remove(DOMAIN, SERVICE_REMOVE_URL)
        hass.services.async_remove(DOMAIN, SERVICE_ENABLE_URL)
        hass.services.async_remove(DOMAIN, SERVICE_DISABLE_URL)
        hass.services.async_remove(DOMAIN, SERVICE_REFRESH)

    return unload_ok
