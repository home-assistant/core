"""The forked_daapd component."""

from pyforked_daapd import ForkedDaapdAPI

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import ForkedDaapdConfigEntry, ForkedDaapdUpdater

PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: ForkedDaapdConfigEntry) -> bool:
    """Set up forked-daapd from a config entry by forwarding to platform."""
    host: str = entry.data[CONF_HOST]
    port: int = entry.data[CONF_PORT]
    password: str = entry.data[CONF_PASSWORD]
    forked_daapd_api = ForkedDaapdAPI(
        async_get_clientsession(hass), host, port, password
    )
    forked_daapd_updater = ForkedDaapdUpdater(hass, forked_daapd_api, entry.entry_id)
    entry.runtime_data = forked_daapd_updater
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ForkedDaapdConfigEntry
) -> bool:
    """Remove forked-daapd component."""
    status = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if status:
        if websocket_handler := entry.runtime_data.websocket_handler:
            websocket_handler.cancel()
    return status
