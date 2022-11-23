"""Config flow for qBittorrent."""
from __future__ import annotations

from typing import Any

from qbittorrent.client import LoginRequired
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_NAME, DEFAULT_URL, DOMAIN
from .helpers import setup_client


class QbittorrentConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for the qBittorrent integration."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a user-initiated config flow."""
        errors = {}

        if user_input is not None:
            for entry in self._async_current_entries():
                if user_input[CONF_URL] == entry.data[CONF_URL]:
                    return self.async_abort(reason="already_configured")
            try:
                await self.hass.async_add_executor_job(
                    setup_client,
                    user_input[CONF_URL],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    user_input[CONF_VERIFY_SSL],
                )
            except LoginRequired:
                errors = {"base": "invalid_auth"}
            except RequestException:
                errors = {"base": "cannot_connect"}
            if not errors:
                await self.async_set_unique_id(
                    user_input[CONF_URL], raise_on_progress=False
                )
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_URL, default=DEFAULT_URL): str,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_VERIFY_SSL, default=True): bool,
                }
            ),
            errors=errors,
        )
