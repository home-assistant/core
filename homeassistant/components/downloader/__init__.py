"""Support for functionality to download files."""

from __future__ import annotations

import os

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import _LOGGER, CONF_DOWNLOAD_DIR
from .services import async_setup_services


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Listen for download events to download files."""
    download_path = entry.data[CONF_DOWNLOAD_DIR]

    # If path is relative, we assume relative to Home Assistant config dir
    if not os.path.isabs(download_path):
        download_path = hass.config.path(download_path)
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_DOWNLOAD_DIR: download_path}
        )

    if not await hass.async_add_executor_job(os.path.isdir, download_path):
        _LOGGER.error(
            "Download path %s does not exist. File Downloader not active", download_path
        )
        return False

    async_setup_services(hass)

    return True
