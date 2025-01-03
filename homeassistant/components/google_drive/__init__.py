"""The Google Drive integration."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.util.hass_dict import HassKey

from .api import AsyncConfigEntryAuth
from .const import DOMAIN

DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(
    f"{DOMAIN}.backup_agent_listeners"
)

type GoogleDriveConfigEntry = ConfigEntry[AsyncConfigEntryAuth]


async def async_setup_entry(hass: HomeAssistant, entry: GoogleDriveConfigEntry) -> bool:
    """Set up Google Drive from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)
    auth = AsyncConfigEntryAuth(hass, session)
    await auth.check_and_refresh_token()
    entry.runtime_data = auth
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GoogleDriveConfigEntry
) -> bool:
    """Unload a config entry."""
    hass.async_create_task(_notify_backup_listeners(hass), eager_start=False)
    return True


async def _notify_backup_listeners(hass: HomeAssistant) -> None:
    for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
        listener()
