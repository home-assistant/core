"""Config flow for Telegram."""

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME

from . import DOMAIN
from .notify import CONF_CHAT_ID


class TelgramConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Telegram."""

    VERSION = 1

    # triggered by async_setup() from __init__.py
    async def async_step_import(self, import_data: dict[str, str]) -> ConfigFlowResult:
        """Handle import of config entry from configuration.yaml."""
        return await self.async_step_user(import_data)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(f"{user_input[CONF_NAME]}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"{user_input[CONF_NAME]} ({user_input[CONF_CHAT_ID]})",
                data={
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_CHAT_ID: user_input[CONF_CHAT_ID],
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): str,
                    vol.Required(CONF_CHAT_ID): vol.Coerce(int),
                }
            ),
            errors=errors,
        )
