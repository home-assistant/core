"""The Invoxia (unofficial) integration."""
from __future__ import annotations

import asyncio

import gps_tracker

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_ENTITIES, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import CLIENT, COORDINATORS, DOMAIN, TRACKERS
from .coordinator import GpsTrackerCoordinator
from .helpers import get_invoxia_client

PLATFORM = Platform.DEVICE_TRACKER


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up GPS Tracker from a config entry."""
    hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})

    config = gps_tracker.Config(
        password=entry.data[CONF_PASSWORD],
        username=entry.data[CONF_EMAIL],
    )

    client = get_invoxia_client(hass, config)

    try:
        trackers: list[gps_tracker.Tracker] = await client.get_trackers()
    except gps_tracker.client.exceptions.UnauthorizedQuery as err:
        raise ConfigEntryAuthFailed(err) from err
    except gps_tracker.client.exceptions.GpsTrackerException as err:
        raise ConfigEntryNotReady(err) from err

    coordinators = [
        GpsTrackerCoordinator(hass, client, tracker) for tracker in trackers
    ]

    await asyncio.gather(
        *[
            coordinator.async_config_entry_first_refresh()
            for coordinator in coordinators
        ]
    )

    # Store client to properly close it when unloading
    hass.data[DOMAIN][entry.entry_id] = {
        # Store client to properly close it when unloading
        CLIENT: client,
        # Store coordinators for device_tracker setup
        COORDINATORS: coordinators,
        # Store entities for access in tests (for now)
        CONF_ENTITIES: [],
        # Store trackers for device_tracker setup
        TRACKERS: trackers,
    }

    await hass.config_entries.async_forward_entry_setup(entry, PLATFORM)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORM):
        await hass.data[DOMAIN][entry.entry_id][CLIENT].close()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
