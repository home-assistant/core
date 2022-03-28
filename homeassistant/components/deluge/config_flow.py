"""Config flow for the Deluge integration."""
from __future__ import annotations

import logging
import socket
from ssl import SSLError
from typing import Any

from deluge_client.client import DelugeRPCClient
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SOURCE,
    CONF_USERNAME,
)
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_WEB_PORT,
    DEFAULT_NAME,
    DEFAULT_RPC_PORT,
    DEFAULT_WEB_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class DelugeFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Deluge."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        title = None

        if user_input is not None:
            if CONF_NAME in user_input:
                title = user_input.pop(CONF_NAME)
            if (error := await self.validate_input(user_input)) is None:
                for entry in self._async_current_entries():
                    if (
                        user_input[CONF_HOST] == entry.data[CONF_HOST]
                        and user_input[CONF_PORT] == entry.data[CONF_PORT]
                    ):
                        if self.context.get(CONF_SOURCE) == SOURCE_REAUTH:
                            self.hass.config_entries.async_update_entry(
                                entry, data=user_input
                            )
                            await self.hass.config_entries.async_reload(entry.entry_id)
                            return self.async_abort(reason="reauth_successful")
                        return self.async_abort(reason="already_configured")
                return self.async_create_entry(
                    title=title or DEFAULT_NAME,
                    data=user_input,
                )
            errors["base"] = error
        user_input = user_input or {}
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=user_input.get(CONF_HOST)): cv.string,
                vol.Required(
                    CONF_USERNAME, default=user_input.get(CONF_USERNAME)
                ): cv.string,
                vol.Required(CONF_PASSWORD, default=""): cv.string,
                vol.Optional(
                    CONF_PORT, default=user_input.get(CONF_PORT, DEFAULT_RPC_PORT)
                ): int,
                vol.Optional(
                    CONF_WEB_PORT,
                    default=user_input.get(CONF_WEB_PORT, DEFAULT_WEB_PORT),
                ): int,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(self, config: dict[str, Any]) -> FlowResult:
        """Handle a reauthorization flow request."""
        return await self.async_step_user()

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        if CONF_MONITORED_VARIABLES in config:
            config.pop(CONF_MONITORED_VARIABLES)
        config[CONF_WEB_PORT] = DEFAULT_WEB_PORT

        for entry in self._async_current_entries():
            if entry.data[CONF_HOST] == config[CONF_HOST]:
                _LOGGER.warning(
                    "Deluge yaml config has been imported. Please remove it"
                )
                return self.async_abort(reason="already_configured")
        return await self.async_step_user(config)

    async def validate_input(self, user_input: dict[str, Any]) -> str | None:
        """Handle common flow input validation."""
        host = user_input[CONF_HOST]
        port = user_input[CONF_PORT]
        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]
        api = DelugeRPCClient(
            host=host, port=port, username=username, password=password
        )
        try:
            await self.hass.async_add_executor_job(api.connect)
        except (
            ConnectionRefusedError,
            socket.timeout,
            SSLError,
        ):
            return "cannot_connect"
        except Exception as ex:  # pylint:disable=broad-except
            if type(ex).__name__ == "BadLoginError":
                return "invalid_auth"  # pragma: no cover
            return "unknown"
        return None
