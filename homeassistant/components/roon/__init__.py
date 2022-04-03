"""Roon (www.roonlabs.com) component."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .server import RoonServer


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a roonserver from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    host = entry.data[CONF_HOST]
    roonserver = RoonServer(hass, entry)

    if not await roonserver.async_setup():
        return False

    hass.data[DOMAIN][entry.entry_id] = roonserver
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="Roonlabs",
        name=host,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    roonserver = hass.data[DOMAIN].pop(entry.entry_id)
    return await roonserver.async_reset()
