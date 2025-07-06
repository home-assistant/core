"""Config flow for Datadog."""

from typing import Any

from datadog import DogStatsd
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

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
                DogStatsd(user_input["host"], user_input["port"], user_input["prefix"])
            )
            if not success:
                errors["base"] = "cannot_connect"
            else:
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return DatadogOptionsFlowHandler(config_entry)


class DatadogOptionsFlowHandler(OptionsFlow):
    """Handle Datadog options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the Datadog options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data = {**self._config_entry.data, **self._config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("host", default=data["host"]): str,
                    vol.Required("port", default=data["port"]): int,
                    vol.Required("prefix", default=data["prefix"]): str,
                    vol.Required("rate", default=data["rate"]): int,
                }
            ),
        )
