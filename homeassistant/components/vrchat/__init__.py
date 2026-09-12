"""The VRChat integration."""

import logging
from typing import cast

from homeassistant.const import CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant

from .api import VRChatAPI
from .coordinator import VRChatAccountDataCoordinator, VRChatConfigEntry
from .store import VRChatAuthCookieStore, VRChatConfigData, get_vrchat_auth_cookie_store

_PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: VRChatConfigEntry) -> bool:
    """Set up VRChat from a config entry."""
    entry.runtime_data = VRChatAccountDataCoordinator(hass, entry)
    await entry.runtime_data.starting_task
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VRChatConfigEntry) -> bool:
    """Unload a VRChat config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, _PLATFORMS):
        await entry.runtime_data.close()
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: VRChatConfigEntry) -> None:
    """Remove VRChat authentication data when removing an entry."""
    unique_id = entry.unique_id
    if unique_id is None:
        return
    cookie_store = get_vrchat_auth_cookie_store(hass, unique_id)
    if CONF_PASSWORD in entry.data:
        try:
            async with VRChatAPI(
                cast(VRChatConfigData, entry.data), await cookie_store.async_load()
            ) as api:
                await api.logout()
        except Exception:
            _LOGGER.exception("Error logging out of VRChat")
    if removed_cookie_store := VRChatAuthCookieStore.pop(unique_id, None):
        await removed_cookie_store.async_remove()
