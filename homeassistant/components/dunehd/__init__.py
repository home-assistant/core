"""The Dune HD component."""
from pdunehd import DuneHDPlayer

from homeassistant.const import CONF_HOST

from .const import DOMAIN

PLATFORMS = ["media_player"]


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    host = entry.data[CONF_HOST]

    player = DuneHDPlayer(host)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = player

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
