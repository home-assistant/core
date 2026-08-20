"""The Marstek integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .client import async_create_udp_client
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Marstek from a config entry."""
    _LOGGER.info("Setting up Marstek config entry: %s", entry.title)

    udp_client = await async_create_udp_client(hass)
    host = entry.data[CONF_HOST]
    try:
        device_info = await udp_client.get_device_info(host)
    except (TimeoutError, OSError, TypeError, ValueError) as err:
        await udp_client.async_cleanup()
        raise ConfigEntryNotReady(
            f"Unable to connect to Marstek device at {host}"
        ) from err

    if not isinstance(device_info, dict):
        await udp_client.async_cleanup()
        raise ConfigEntryNotReady(f"Marstek device at {host} returned invalid data")

    entry.runtime_data = udp_client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Marstek config entry: %s", entry.title)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Cleanup global UDP client if this is the last entry. The entry being
    # unloaded is still present in async_entries() at this point, so check
    # for a single remaining entry rather than an empty list.
    if unload_ok and len(hass.config_entries.async_entries(DOMAIN)) == 1:
        await entry.runtime_data.async_cleanup()

    return unload_ok
