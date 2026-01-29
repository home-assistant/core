"""The Hegel integration."""

from __future__ import annotations

import logging

from hegel_ip_client import HegelClient
from hegel_ip_client.exceptions import HegelConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DEFAULT_PORT

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]
_LOGGER = logging.getLogger(__name__)

type HegelConfigEntry = ConfigEntry[HegelClient]


async def async_setup_entry(hass: HomeAssistant, entry: HegelConfigEntry) -> bool:
    """Set up the Hegel integration."""
    host = entry.data[CONF_HOST]

    # Create and test client connection
    client = HegelClient(host, DEFAULT_PORT)

    try:
        # Test connection before proceeding with setup
        await client.start()
        await client.ensure_connected(timeout=10.0)
        _LOGGER.debug("Successfully connected to Hegel at %s:%s", host, DEFAULT_PORT)
    except (HegelConnectionError, TimeoutError, OSError) as err:
        _LOGGER.error(
            "Failed to connect to Hegel at %s:%s: %s", host, DEFAULT_PORT, err
        )
        await client.stop()  # Clean up
        raise ConfigEntryNotReady(
            f"Unable to connect to Hegel amplifier at {host}:{DEFAULT_PORT}"
        ) from err

    # Store client in runtime_data
    entry.runtime_data = client

    async def _async_close_client(event):
        await client.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_close_client)
    )

    # Forward setup to supported platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HegelConfigEntry) -> bool:
    """Unload a Hegel config entry and stop active client connection."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        client = entry.runtime_data
        _LOGGER.debug("Stopping Hegel client for %s", entry.title)
        try:
            await client.stop()
        except (HegelConnectionError, OSError) as err:
            _LOGGER.warning("Error while stopping Hegel client: %s", err)

    return unload_ok
