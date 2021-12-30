"""Config flow to configure the Whois integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_DOMAIN, CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class WhoisFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Whois."""

    VERSION = 1

    imported_name: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_DOMAIN].lower())
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self.imported_name or user_input[CONF_DOMAIN],
                data={
                    CONF_DOMAIN: user_input[CONF_DOMAIN].lower(),
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DOMAIN): str,
                }
            ),
        )

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Handle a flow initialized by importing a config."""
        self.imported_name = config[CONF_NAME]
        return await self.async_step_user(
            user_input={
                CONF_DOMAIN: config[CONF_DOMAIN],
            }
        )
