"""The VRChat integration."""

import logging

from vrchatapi.highlevel import VRChatAPI

from homeassistant.const import CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant

from .const import USER_AGENT
from .coordinator import VRChatAccountDataCoordinator, VRChatConfigEntry
from .store import VRChatAuthCookieStore, get_vrchat_auth_cookie_store

_PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: VRChatConfigEntry) -> bool:
    """Set up VRChat from a config entry."""
    entry.runtime_data = VRChatAccountDataCoordinator(hass, entry)
    try:
        await entry.runtime_data.async_start()
    except BaseException:
        await entry.runtime_data.close()
        raise

    async def async_stop(event: Event) -> None:
        await entry.runtime_data.close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop)
    )
    try:
        await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    except BaseException:
        await entry.runtime_data.close()
        raise
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
                entry.data,
                await cookie_store.async_load(),
                user_agent=USER_AGENT,
            ) as api:
                await api.logout()
        except Exception:
            _LOGGER.exception("Error logging out of VRChat")
    if removed_cookie_store := VRChatAuthCookieStore.pop(unique_id, None):
        await removed_cookie_store.async_remove()
