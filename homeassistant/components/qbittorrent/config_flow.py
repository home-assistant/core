"""Config flow for qBittorrent."""
from __future__ import annotations

import logging
from typing import Any

from qbittorrent.client import LoginRequired
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_CREATE_TORRENT_SENSORS, DEFAULT_NAME, DEFAULT_URL, DOMAIN
from .helpers import setup_client

_LOGGER = logging.getLogger(__name__)

USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default=DEFAULT_URL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
    }
)

OPTIONS_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_CREATE_TORRENT_SENSORS, default=False): bool,
    }
)


class QbittorrentConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for the qBittorrent integration (for initial configuration)."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a user-initiated config flow."""
        errors = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})
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
            else:
                return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

        schema = self.add_suggested_values_to_schema(USER_DATA_SCHEMA, user_input)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> QbittorrentOptionsFlowHandler:
        """Get the options flow for this handler."""
        return QbittorrentOptionsFlowHandler(config_entry)


class QbittorrentOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """Options flow for the qBittorrent integration (for modifying options once set up)."""

    async def async_step_init(self, user_input=None):
        """Manage the qBittorrent options."""
        return await self.async_step_qbittorrent_options(user_input)

    async def async_step_qbittorrent_options(self, user_input=None):
        """Manage the qBittorrent options once an entry has already been initially configured."""
        if not user_input:
            schema = self.add_suggested_values_to_schema(
                OPTIONS_DATA_SCHEMA, self.config_entry.options
            )
            return self.async_show_form(
                step_id="qbittorrent_options", data_schema=schema
            )

        return self.async_create_entry(title=DEFAULT_NAME, data=user_input)
