"""The forked_daapd component."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, HASS_DATA_REMOVE_LISTENERS_KEY, HASS_DATA_UPDATER_KEY

PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up forked-daapd from a config entry by forwarding to platform."""
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
        for remove_listener in hass.data[DOMAIN][entry.entry_id][
            HASS_DATA_REMOVE_LISTENERS_KEY
        ]:
            remove_listener()
        del hass.data[DOMAIN][entry.entry_id]
        if not hass.data[DOMAIN]:
            del hass.data[DOMAIN]
    return status
