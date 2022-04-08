"""The filesize component."""
from __future__ import annotations

import logging
import pathlib

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FILE_PATH
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""

    path = entry.data[CONF_FILE_PATH]
    get_path = await hass.async_add_executor_job(pathlib.Path, path)

    if not get_path.exists() and not get_path.is_file():
        raise ConfigEntryNotReady(f"Can not access file {path}")

    if not hass.config.is_allowed_path(path):
        raise ConfigEntryNotReady(f"Filepath {path} is not valid or allowed")

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
