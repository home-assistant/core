"""The Rollease Acmeda Automate integration."""
import asyncio

from homeassistant import config_entries, core

from .const import DOMAIN
from .hub import PulseHub

CONF_HUBS = "hubs"

PLATFORMS = ["cover", "sensor"]


async def async_setup(hass: core.HomeAssistant, config: dict):
    """Set up the Rollease Acmeda Automate component."""
    return True


async def async_setup_entry(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Set up Rollease Acmeda Automate hub from a config entry."""
    hub = PulseHub(hass, config_entry)

    if not await hub.async_setup():
        return False

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = hub

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    return True


async def async_unload_entry(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Unload a config entry."""
    hub = hass.data[DOMAIN][config_entry.entry_id]

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if not await hub.async_reset():
        return False

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
