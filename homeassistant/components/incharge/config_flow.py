"""Config flow for growatt server integration."""
from http import HTTPStatus
from typing import Any

from incharge.api import InCharge
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, NAME


class InChargeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow class."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise growatt server flow."""
        self.data: dict[str, Any] = {}
        self.api: InCharge | None = None

    @callback
    def _async_show_user_form(self, errors: dict[str, str] | None = None):
        """Show the form to the user."""
        data_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the start of the config flow."""
        if not user_input:
            return self._async_show_user_form()

        self.api = InCharge(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
        login_response = await self.hass.async_add_executor_job(self.api.authenticate)
        if login_response.status_code == HTTPStatus.NOT_FOUND:
            return self._async_show_user_form({"base": "cannot_connect"})
        if login_response.status_code != HTTPStatus.OK:
            return self._async_show_user_form({"base": "invalid_auth"})
        self.data = user_input

        return self.async_create_entry(title=NAME, data=self.data)
