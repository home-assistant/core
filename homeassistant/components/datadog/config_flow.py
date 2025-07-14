"""Config flow for Datadog."""

from typing import Any

from datadog import DogStatsd
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_PREFIX
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_RATE,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_PREFIX,
    DEFAULT_RATE,
    DOMAIN,
)


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
                self.hass,
                user_input,
            )
            if not success:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"Datadog {user_input['host']}", data={}, options=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Required(CONF_PREFIX, default=DEFAULT_PREFIX): str,
                    vol.Required(CONF_RATE, default=DEFAULT_RATE): int,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_config: dict) -> ConfigFlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_user(import_config)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlow:
        """Get the options flow handler."""
        return DatadogOptionsFlowHandler()


class DatadogOptionsFlowHandler(OptionsFlow):
    """Handle Datadog options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the Datadog options."""
        errors: dict[str, str] = {}
        if user_input:
            success = await validate_datadog_connection(
                self.hass,
                user_input,
            )
            if not success:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(data=user_input)

        data = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=data["host"]): str,
                    vol.Required(CONF_PORT, default=data["port"]): int,
                    vol.Required(CONF_PREFIX, default=data["prefix"]): str,
                    vol.Required(CONF_RATE, default=data["rate"]): int,
                }
            ),
            errors=errors,
        )


async def validate_datadog_connection(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> bool:
    """Attempt to send a test metric to the Datadog agent."""
    try:
        client = DogStatsd(user_input["host"], user_input["port"], user_input["prefix"])
        hass.async_add_executor_job(client.increment, "connection_test")
    except (OSError, ValueError):
        return False
    else:
        return True
