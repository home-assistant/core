"""The yale_smart_alarm component."""
from __future__ import annotations

import asyncio

from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, LOGGER
from .coordinator import YaleDataUpdateCoordinator

PLATFORMS = ["alarm_control_panel"]


async def async_setup_entry(hass, entry):
    """Set up Yale from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    title = entry.title

    coordinator = YaleDataUpdateCoordinator(hass, entry=entry)

    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
    }

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    LOGGER.debug("Loaded entry for %s", title)

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    title = entry.title
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        LOGGER.debug("Unloaded entry for %s", title)
        return unload_ok

    return False
