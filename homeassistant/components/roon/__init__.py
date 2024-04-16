"""Roon (www.roonlabs.com) component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONF_ROON_NAME, DOMAIN
from .server import RoonServer

PLATFORMS = [Platform.EVENT, Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a roonserver from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # fallback to using host for compatibility with older configs
    name = entry.data.get(CONF_ROON_NAME, entry.data[CONF_HOST])

    roonserver = RoonServer(hass, entry)

    if not await roonserver.async_setup():
        return False

    hass.data[DOMAIN][entry.entry_id] = roonserver
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="Roonlabs",
        name=f"Roon Core ({name})",
    )

    # initialize media_player platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False

    roonserver = hass.data[DOMAIN].pop(entry.entry_id)
    return await roonserver.async_reset()
