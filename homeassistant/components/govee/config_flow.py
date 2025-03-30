"""Config flow for Govee Heater integration."""

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_API_KEY, CONF_DEVICE_ID, CONF_SKU, DOMAIN


class GoveeHeaterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Govee Heater."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.api_key: str | None = None
        self.device_id: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.api_key = user_input.get(CONF_API_KEY)
            self.device_id = user_input.get(CONF_DEVICE_ID)
            await self.async_set_unique_id(user_input[CONF_DEVICE_ID])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Govee", data=user_input)

        # Show the input form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Required(CONF_DEVICE_ID): str,
                    vol.Required(CONF_SKU): str,
                }
            ),
            errors=errors,
        )

    def is_matching(self, other_flow: dict[str, Any]) -> bool:
        """Check if the config entry matches the current configuration."""
        return (
            other_flow.get(CONF_API_KEY) == self.api_key
            or other_flow.get(CONF_DEVICE_ID) == self.device_id
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid authentication."""
