"""The laundrify integration."""

from __future__ import annotations

from laundrify_aio import LaundrifyAPI
from laundrify_aio.exceptions import ApiConnectionException, UnauthorizedException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_POLL_INTERVAL, DOMAIN
from .coordinator import LaundrifyUpdateCoordinator

PLATFORMS = [Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up laundrify from a config entry."""

    session = async_get_clientsession(hass)
    api_client = LaundrifyAPI(entry.data[CONF_ACCESS_TOKEN], session)

    try:
        await api_client.validate_token()
    except UnauthorizedException as err:
        raise ConfigEntryAuthFailed("Invalid authentication") from err
    except ApiConnectionException as err:
        raise ConfigEntryNotReady("Cannot reach laundrify API") from err

    coordinator = LaundrifyUpdateCoordinator(hass, api_client, DEFAULT_POLL_INTERVAL)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api_client,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
