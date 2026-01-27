"""The Airtouch 5 integration."""

from __future__ import annotations

import logging

from airtouch5py.airtouch5_simple_client import Airtouch5SimpleClient
from airtouch5py.discovery import AirtouchDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

# device_registry as dr, Maybe needed in migration. If not can be removed later.

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.COVER]

_LOGGER = logging.getLogger(__name__)

type Airtouch5ConfigEntry = ConfigEntry[Airtouch5SimpleClient]


async def async_setup_entry(hass: HomeAssistant, entry: Airtouch5ConfigEntry) -> bool:
    """Set up Airtouch 5 from a config entry."""

    # Create API instance
    host = entry.data[CONF_HOST]

    # So for any device that is created using the old flow (AC_0) is the ID. So we just assume that.
    device = AirtouchDevice(
        host,
        entry.data.get("console_id", ""),
        entry.data.get("model", "AirTouch5"),
        entry.data.get("system_id", 0),
        entry.data.get("name", "Unknown Device"),
    )
    client = Airtouch5SimpleClient(host)
    client.device = device

    # Connect to the API
    try:
        await client.connect_and_stay_connected()
    except TimeoutError as t:
        raise ConfigEntryNotReady from t

    # Store an API object for your platforms to access
    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: Airtouch5ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        client = entry.runtime_data
        await client.disconnect()
        client.ac_status_callbacks.clear()
        client.connection_state_callbacks.clear()
        client.data_packet_callbacks.clear()
        client.zone_status_callbacks.clear()
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.info(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )
    return True
