"""The laundrify integration."""
from __future__ import annotations

from laundrify_aio import LaundrifyAPI
from laundrify_aio.exceptions import ApiConnectionException, UnauthorizedException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, DOMAIN
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

    poll_interval = entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
    coordinator = LaundrifyUpdateCoordinator(hass, api_client, poll_interval)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api_client,
        "coordinator": coordinator,
    }

    entry.async_on_unload(entry.add_update_listener(options_update_listener))

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def options_update_listener(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
