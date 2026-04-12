"""The Aquarite integration."""

from __future__ import annotations

from aioaquarite import AquariteAuth, AquariteClient, AquariteError, AuthenticationError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import AquariteDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


type AquariteConfigEntry = ConfigEntry[AquariteDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: AquariteConfigEntry) -> bool:
    """Set up Aquarite from a config entry."""
    user_config = entry.data
    session = async_get_clientsession(hass)
    pool_id: str = user_config["pool_id"]

    auth = AquariteAuth(session, user_config[CONF_USERNAME], user_config[CONF_PASSWORD])
    try:
        await auth.authenticate()
    except AuthenticationError as exc:
        raise ConfigEntryAuthFailed from exc
    except AquariteError as exc:
        raise ConfigEntryNotReady from exc

    api = AquariteClient(auth)
    coordinator = AquariteDataUpdateCoordinator(hass, entry, auth, api, pool_id)

    # Initial coordinator refresh and subscription
    await coordinator.async_config_entry_first_refresh()
    await coordinator.subscribe()

    # Start background tasks (token refresh and health check)
    await coordinator.setup_tasks()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AquariteConfigEntry) -> bool:
    """Unload Aquarite config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unloaded:
        await entry.runtime_data.async_shutdown()

    return unloaded
