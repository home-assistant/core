"""The yale_smart_alarm component."""
from __future__ import annotations

import asyncio

from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, LOGGER
from .coordinator import YaleDataUpdateCoordinator


async def async_setup(hass, config):
    """No setup from yaml for Yale."""
    return True


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

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "alarm_control_panel")
    )

    hass.async_create_task(hass.config_entries.async_forward_entry_setup(entry, "lock"))

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "binary_sensor")
    )

    LOGGER.debug("Loaded entry for %s", title)

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""

    Platforms = []
    Platforms.append("alarm_control_panel")
    if hass.data[DOMAIN][entry.entry_id]["coordinator"].data["lock"] != []:
        Platforms.append("lock")
    if hass.data[DOMAIN][entry.entry_id]["coordinator"].data["door_window"] != []:
        Platforms.append("binary_sensor")

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in Platforms
            ]
        )
    )

    title = entry.title
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        LOGGER.debug("Unloaded entry for %s", title)
        return unload_ok

    return False
