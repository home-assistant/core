"""Config flow for Watergate."""

import voluptuous as vol
from watergate_local_api.watergate_api import WatergateLocalApiClient

from homeassistant.components.webhook import async_generate_id as webhook_generate_id
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME, CONF_WEBHOOK_ID

from .const import DOMAIN

WATERGATE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_IP_ADDRESS): str,
    }
)


class WatergateConfigFlow(ConfigFlow, domain=DOMAIN):
    """Watergate config flow."""

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not await self.validate_connection(user_input[CONF_IP_ADDRESS]):
                errors[CONF_IP_ADDRESS] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={**user_input, CONF_WEBHOOK_ID: webhook_generate_id()},
                )

        return self.async_show_form(
            step_id="user", data_schema=WATERGATE_SCHEMA, errors=errors
        )

    async def validate_connection(self, ip_address: str):
        """Validate the connection to the Watergate device."""
        try:
            return (
                await WatergateLocalApiClient(ip_address).async_get_device_state()
                is not None
            )
        except Exception:  # noqa: BLE001
            return False
