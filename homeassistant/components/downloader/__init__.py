"""Support for functionality to download files."""

import os

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_DOWNLOAD_DIR, DOMAIN
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Downloader component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Listen for download events to download files."""
    download_path = entry.data[CONF_DOWNLOAD_DIR]

    # If path is relative, we assume relative to Home Assistant config dir
    if not os.path.isabs(download_path):
        download_path = hass.config.path(download_path)
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_DOWNLOAD_DIR: download_path}
        )

    if not await hass.async_add_executor_job(os.path.isdir, download_path):
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="download_path_not_found",
            translation_placeholders={"path": download_path},
        )
