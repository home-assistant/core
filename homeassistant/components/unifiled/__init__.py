"""Unifi LED Lights integration."""
import logging

from unifiled import unifiled

from homeassistant.exceptions import PlatformNotReady

from .const import KEY_API

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the unifiled integration."""
    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry for unifiled."""

    # Assign configuration variables.
    host = entry.data["host"]
    port = entry.data["port"]
    username = entry.data["username"]
    password = entry.data["password"]

    api = unifiled(host, port, username=username, password=password)

    # Verify that passed in configuration works
    if not api.getloginstate():
        _LOGGER.error("Could not connect to unifiled controller")
        raise PlatformNotReady()

    hass.data.setdefault(KEY_API, {})[entry.entry_id] = api

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "light")
    )

    return True
