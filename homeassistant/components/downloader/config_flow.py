"""Config flow for Downloader integration."""

from __future__ import annotations

import os
from typing import Any

import voluptuous as vol

from homeassistant import exceptions
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import config_validation as cv

from .const import _LOGGER, CONF_DOWNLOAD_DIR, DEFAULT_NAME, DOMAIN


class DownloaderConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Downloader."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self._validate_input(user_input)
            except DirectoryDoesNotExist:
                errors["base"] = "directory_does_not_exist"
            else:
                return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DOWNLOAD_DIR): cv.string,
                }
            ),
            errors=errors,
        )

    async def _validate_input(self, user_input: dict[str, Any]) -> None:
        """Validate the user input if the directory exists."""
        download_path = user_input[CONF_DOWNLOAD_DIR]
        if not os.path.isabs(download_path):
            download_path = self.hass.config.path(download_path)

        if not await self.hass.async_add_executor_job(os.path.isdir, download_path):
            _LOGGER.error(
                "Download path %s does not exist. File Downloader not active",
                download_path,
            )
            raise DirectoryDoesNotExist


class DirectoryDoesNotExist(exceptions.HomeAssistantError):
    """Error to indicate the specified download directory does not exist."""
