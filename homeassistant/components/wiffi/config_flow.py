"""Config flow for wiffi component.

Used by UI to setup a wiffi integration.
"""

from __future__ import annotations

import errno
from typing import Any

import voluptuous as vol
from wiffi import WiffiTcpServer

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PORT, CONF_TIMEOUT
from homeassistant.core import callback

from .const import DEFAULT_PORT, DEFAULT_TIMEOUT, DOMAIN


class WiffiFlowHandler(ConfigFlow, domain=DOMAIN):
    """Wiffi server setup config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Create Wiffi server setup option flow."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the start of the config flow.

        Called after wiffi integration has been selected in the 'add integration
        UI'. The user_input is set to None in this case. We will open a config
        flow form then.
        This function is also called if the form has been submitted. user_input
        contains a dict with the user entered values then.
        """
        if user_input is None:
            return self._async_show_form()

        # received input from form or configuration.yaml
        self._async_abort_entries_match(user_input)

        try:
            # try to start server to check whether port is in use
            server = WiffiTcpServer(user_input[CONF_PORT])
            await server.start_server()
            await server.close_server()
            return self.async_create_entry(
                title=f"Port {user_input[CONF_PORT]}", data=user_input
            )
        except OSError as exc:
            if exc.errno == errno.EADDRINUSE:
                return self.async_abort(reason="addr_in_use")
            return self.async_abort(reason="start_server_failed")

    @callback
    def _async_show_form(self, errors=None):
        """Show the config flow form to the user."""
        data_schema = {vol.Required(CONF_PORT, default=DEFAULT_PORT): int}

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors=errors or {}
        )


class OptionsFlowHandler(OptionsFlow):
    """Wiffi server setup option flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, int] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_TIMEOUT,
                        default=self.config_entry.options.get(
                            CONF_TIMEOUT, DEFAULT_TIMEOUT
                        ),
                    ): int,
                }
            ),
        )
