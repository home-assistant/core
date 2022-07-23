"""Adds config flow for Sutro."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import SutroApiClient
from .const import CONF_TOKEN, DOMAIN, PLATFORMS


class SutroFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for sutro."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._errors = {}

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            data = await self._test_credentials(user_input[CONF_TOKEN])
            if data:
                return self.async_create_entry(
                    title=f"{data['me']['firstName']}'s Pool/Spa", data=user_input
                )

            self._errors["base"] = "auth"
            return await self._show_config_form(user_input)

        return await self._show_config_form(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get options flow for configuring Sutro."""
        return SutroOptionsFlowHandler(config_entry)

    async def _show_config_form(self, user_input):  # pylint: disable=unused-argument
        """Show the configuration form to edit location data."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
            errors=self._errors,
        )

    async def _test_credentials(self, token) -> dict | None:
        """Return true if credentials is valid."""
        try:
            session = async_create_clientsession(self.hass)
            client = SutroApiClient(token, session)
            return await client.async_get_data()
        except Exception:  # pylint: disable=broad-except
            pass
        return None


class SutroOptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options handler for sutro."""

    def __init__(self, config_entry):
        """Initialize HACS options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(
        self, user_input=None
    ) -> FlowResult:  # pylint: disable=unused-argument
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self.options.update(user_input)
            return await self._update_options()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(x, default=self.options.get(x, True)): bool
                    for x in sorted(PLATFORMS)
                }
            ),
        )

    async def _update_options(self):
        """Update config entry options."""
        return self.async_create_entry(
            title=self.config_entry.data.get(CONF_TOKEN), data=self.options
        )
