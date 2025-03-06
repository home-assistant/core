"""The forked_daapd component."""

from pyforked_daapd import ForkedDaapdAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, HASS_DATA_UPDATER_KEY
from .coordinator import ForkedDaapdUpdater

PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up forked-daapd from a config entry by forwarding to platform."""
    host: str = entry.data[CONF_HOST]
    port: int = entry.data[CONF_PORT]
    password: str = entry.data[CONF_PASSWORD]
    forked_daapd_api = ForkedDaapdAPI(
        async_get_clientsession(hass), host, port, password
    )
    forked_daapd_updater = ForkedDaapdUpdater(hass, forked_daapd_api, entry.entry_id)
    if not hass.data.get(DOMAIN):
        hass.data[DOMAIN] = {entry.entry_id: {}}
    hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})[
        HASS_DATA_UPDATER_KEY
    ] = forked_daapd_updater
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove forked-daapd component."""
    status = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if status and hass.data.get(DOMAIN) and hass.data[DOMAIN].get(entry.entry_id):
        if websocket_handler := hass.data[DOMAIN][entry.entry_id][
            HASS_DATA_UPDATER_KEY
        ].websocket_handler:
            websocket_handler.cancel()
        del hass.data[DOMAIN][entry.entry_id]
        if not hass.data[DOMAIN]:
            del hass.data[DOMAIN]
    return status
