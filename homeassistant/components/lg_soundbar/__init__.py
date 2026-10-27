"""The lg_soundbar component."""

import logging

from homeassistant import config_entries, core
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.exceptions import ConfigEntryNotReady

from .config_flow import test_connect

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> None:
    """Set up platform from a ConfigEntry."""
    # Verify the device is reachable with the given
    # config before setting up the platform
    try:
        await hass.async_add_executor_job(
            test_connect, entry.data[CONF_HOST], entry.data[CONF_PORT]
        )
    except ConnectionError as err:
        raise ConfigEntryNotReady from err

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
