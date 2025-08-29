"""My Curtain curtain integration"""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .api import MyCurtainApiClient
from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set configuration items."""
    # Create API client
    _LOGGER.info("launch")
    client = MyCurtainApiClient(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )

    # Store the client instance
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client

    # Set up the platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set update options
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Uninstall configuration items."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Listener for updating configuration items."""
    await hass.config_entries.async_reload(entry.entry_id)
