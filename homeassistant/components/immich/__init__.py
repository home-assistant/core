"""The Immich integration."""

from __future__ import annotations

from aioimmich import Immich
from aioimmich.const import CONNECT_ERRORS
from aioimmich.exceptions import ImmichUnauthorizedError

from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import ImmichConfigEntry, ImmichDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ImmichConfigEntry) -> bool:
    """Set up Immich from a config entry."""

    session = async_get_clientsession(hass, entry.data[CONF_VERIFY_SSL])
    immich = Immich(
        session,
        entry.data[CONF_API_KEY],
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_SSL],
    )

    try:
        user_info = await immich.users.async_get_my_user()
    except ImmichUnauthorizedError as err:
        raise ConfigEntryAuthFailed from err
    except CONNECT_ERRORS as err:
        raise ConfigEntryNotReady from err

    coordinator = ImmichDataUpdateCoordinator(hass, entry, immich, user_info.is_admin)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ImmichConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
