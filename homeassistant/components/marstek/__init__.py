"""The Marstek integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .client import async_get_udp_client
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Marstek from a config entry."""
    _LOGGER.info("Setting up Marstek config entry: %s", entry.title)

    udp_client = await async_get_udp_client(hass)
    host = entry.data[CONF_HOST]
    try:
        device_info = await udp_client.get_device_info(host)
    except (TimeoutError, OSError, TypeError, ValueError) as err:
        raise ConfigEntryNotReady(
            f"Unable to connect to Marstek device at {host}"
        ) from err

    if not isinstance(device_info, dict):
        raise ConfigEntryNotReady(f"Marstek device at {host} returned invalid data")

    entry.runtime_data = udp_client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Marstek config entry: %s", entry.title)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Cleanup global UDP client if no entries remain
    if unload_ok and not hass.config_entries.async_entries(DOMAIN):
        client = hass.data.get(DOMAIN, {}).pop("udp_client", None)
        if client:
            await client.async_cleanup()

    return unload_ok
