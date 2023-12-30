"""Config flow for Tedee integration."""
from typing import Any

from pytedee_async import (
    TedeeAuthException,
    TedeeClient,
    TedeeClientException,
    TedeeLocalAuthException,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_LOCAL_ACCESS_TOKEN, DOMAIN, NAME


class TedeeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tedee."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            local_access_token = user_input[CONF_LOCAL_ACCESS_TOKEN]
            tedee_client = TedeeClient(local_token=local_access_token, local_ip=host)
            try:
                local_bridge = await tedee_client.get_local_bridge()
            except (TedeeAuthException, TedeeLocalAuthException):
                errors[CONF_LOCAL_ACCESS_TOKEN] = "invalid_api_key"
            except TedeeClientException:
                errors[CONF_HOST] = "invalid_host"

            else:
                await self.async_set_unique_id(local_bridge.serial)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=NAME, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_LOCAL_ACCESS_TOKEN): str,
                }
            ),
            errors=errors,
        )
