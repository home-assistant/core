"""The Rollease Acmeda Automate integration."""

from homeassistant import config_entries, core

from .const import DOMAIN
from .hub import PulseHub

CONF_HUBS = "hubs"

PLATFORMS = ["cover", "sensor"]


async def async_setup_entry(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Set up Rollease Acmeda Automate hub from a config entry."""
    hub = PulseHub(hass, config_entry)

    if not await hub.async_setup():
        return False

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = hub

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Unload a config entry."""
    hub = hass.data[DOMAIN][config_entry.entry_id]

    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if not await hub.async_reset():
        return False

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
