"""Config flow for Downloader integration."""
from __future__ import annotations

import os

from aioesphomeapi import Any
from aioskybell import _LOGGER
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import CONF_DOWNLOAD_DIR, DEFAULT_NAME, DOMAIN


class DownloaderConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Downloader."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            # Do checks in the config flow, instead of the init
            if not os.path.isabs(user_input[CONF_DOWNLOAD_DIR]):
                download_path = self.hass.config.path(user_input[CONF_DOWNLOAD_DIR])

            if not os.path.isdir(download_path):
                _LOGGER.error(
                    "Download path %s does not exist. File Downloader not active",
                    download_path,
                )
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DOWNLOAD_DIR): cv.string,
                }
            ),
        )

    async def async_step_import(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by configuration file."""
        async_create_issue(
            self.hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2024.2.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Ping",
            },
        )

        return await self.async_step_user(user_input)
