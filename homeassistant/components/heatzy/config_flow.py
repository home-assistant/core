"""Config flow to configure Heatzy."""
from __future__ import annotations

import logging

from heatzypy import HeatzyClient
from heatzypy.exception import AuthenticationFailed, HeatzyException, HttpRequestFailed
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import DOMAIN

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)

_LOGGER = logging.getLogger(__name__)


class HeatzyFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Heatzy config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input:
            try:
                username = user_input[CONF_USERNAME]
                self._async_abort_entries_match({CONF_USERNAME: username})
                api = HeatzyClient(
                    username,
                    user_input[CONF_PASSWORD],
                    async_create_clientsession(self.hass),
                )
                await api.async_bindings()
            except AuthenticationFailed:
                errors["base"] = "invalid_auth"
            except HttpRequestFailed:
                errors["base"] = "cannot_connect"
            except HeatzyException:
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"{DOMAIN} ({username})", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
