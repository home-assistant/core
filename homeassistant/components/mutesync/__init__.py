"""The mütesync integration."""
from __future__ import annotations

import logging

import async_timeout
import mutesync

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import update_coordinator

from .const import DOMAIN, UPDATE_INTERVAL_IN_MEETING, UPDATE_INTERVAL_NOT_IN_MEETING

PLATFORMS = ["binary_sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up mütesync from a config entry."""
    client = mutesync.PyMutesync(
        entry.data["token"],
        entry.data["host"],
        hass.helpers.aiohttp_client.async_get_clientsession(),
    )

    async def update_data():
        """Update the data."""
        async with async_timeout.timeout(2.5):
            state = await client.get_state()

            if state["muted"] is None or state["in_meeting"] is None:
                raise update_coordinator.UpdateFailed("Got invalid response")

            if state["in_meeting"]:
                coordinator.update_interval = UPDATE_INTERVAL_IN_MEETING
            else:
                coordinator.update_interval = UPDATE_INTERVAL_NOT_IN_MEETING

            return state

    coordinator = hass.data.setdefault(DOMAIN, {})[
        entry.entry_id
    ] = update_coordinator.DataUpdateCoordinator(
        hass,
        logging.getLogger(__name__),
        name=DOMAIN,
        update_interval=UPDATE_INTERVAL_NOT_IN_MEETING,
        update_method=update_data,
    )
    await coordinator.async_config_entry_first_refresh()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
