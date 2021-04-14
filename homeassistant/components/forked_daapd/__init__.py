"""The forked_daapd component."""
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN

from .const import DOMAIN, HASS_DATA_REMOVE_LISTENERS_KEY, HASS_DATA_UPDATER_KEY


async def async_setup_entry(hass, entry):
    """Set up forked-daapd from a config entry by forwarding to platform."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, MP_DOMAIN)
    )
    return True


async def async_unload_entry(hass, entry):
    """Remove forked-daapd component."""
    status = await hass.config_entries.async_forward_entry_unload(entry, MP_DOMAIN)
    if status and hass.data.get(DOMAIN) and hass.data[DOMAIN].get(entry.entry_id):
        hass.data[DOMAIN][entry.entry_id][
            HASS_DATA_UPDATER_KEY
        ].websocket_handler.cancel()
        for remove_listener in hass.data[DOMAIN][entry.entry_id][
            HASS_DATA_REMOVE_LISTENERS_KEY
        ]:
            remove_listener()
        del hass.data[DOMAIN][entry.entry_id]
        if not hass.data[DOMAIN]:
            del hass.data[DOMAIN]
    return status
