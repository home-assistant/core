"""Config flow for the Deluge integration."""
from __future__ import annotations

from collections.abc import Mapping
from ssl import SSLError
from typing import Any

from deluge_client.client import DelugeRPCClient
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow
from homeassistant.const import (
    CONF_HOST,
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


class DelugeFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Deluge."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
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
                    title=DEFAULT_NAME,
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

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle a reauthorization flow request."""
        return await self.async_step_user()

    async def validate_input(self, user_input: dict[str, Any]) -> str | None:
        """Handle common flow input validation."""
        host = user_input[CONF_HOST]
        port = user_input[CONF_PORT]
        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]
        api = DelugeRPCClient(
            host=host, port=port, username=username, password=password, decode_utf8=True
        )
        try:
            await self.hass.async_add_executor_job(api.connect)
        except (ConnectionRefusedError, TimeoutError, SSLError):
            return "cannot_connect"
        except Exception as ex:  # pylint:disable=broad-except
            if type(ex).__name__ == "BadLoginError":
                return "invalid_auth"
            return "unknown"
        return None
