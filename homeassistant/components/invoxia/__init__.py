"""The Invoxia (unofficial) integration."""
from __future__ import annotations

import gps_tracker

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITIES, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import CLIENT, DOMAIN
from .helpers import get_invoxia_client

PLATFORM = Platform.DEVICE_TRACKER


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up GPS Tracker from a config entry."""
    hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})

    config = gps_tracker.Config(
        password=entry.data[CONF_PASSWORD],
        username=entry.data[CONF_USERNAME],
    )

    client = get_invoxia_client(hass, config)

    try:
        await client.get_devices()
    except gps_tracker.client.exceptions.UnauthorizedQuery as err:
        raise ConfigEntryAuthFailed(err) from err
    except gps_tracker.client.exceptions.GpsTrackerException as err:
        raise ConfigEntryNotReady(err) from err

    hass.data[DOMAIN][entry.entry_id][CLIENT] = client
    hass.data[DOMAIN][entry.entry_id][CONF_ENTITIES] = []

    await hass.config_entries.async_forward_entry_setup(entry, PLATFORM)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORM)
    if unload_ok:
        await hass.data[DOMAIN][entry.entry_id][CLIENT].close()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
