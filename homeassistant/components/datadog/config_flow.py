"""Config flow for Datadog."""

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult

from . import validate_datadog_connection
from .const import DEFAULT_HOST, DEFAULT_PORT, DEFAULT_PREFIX, DEFAULT_RATE, DOMAIN


class DatadogConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Datadog."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user config flow."""
        errors: dict[str, str] = {}
        if user_input:
            # Validate connection to Datadog Agent
            success = await validate_datadog_connection(
                user_input["host"],
                user_input["port"],
                user_input["prefix"],
            )
            if not success:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    f"{user_input['host']}:{user_input['port']}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Datadog", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("host", default=DEFAULT_HOST): str,
                    vol.Required("port", default=DEFAULT_PORT): int,
                    vol.Required("prefix", default=DEFAULT_PREFIX): str,
                    vol.Required("rate", default=DEFAULT_RATE): int,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_config: dict) -> ConfigFlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_user(import_config)
