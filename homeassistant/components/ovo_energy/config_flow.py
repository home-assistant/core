"""Config flow to configure the OVO Energy integration."""
import logging

import aiohttp
from ovoenergy.ovoenergy import OVOEnergy
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import CONF_ACCOUNT_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class OVOEnergyFlowHandler(ConfigFlow):
    """Handle a OVO Energy config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize OVO Energy flow."""

    async def _show_setup_form(self, errors=None):
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
            ),
            errors=errors or {},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if user_input is None:
            return await self._show_setup_form()

        errors = {}

        client = OVOEnergy()

        try:
            if (
                await client.authenticate(
                    user_input.get(CONF_USERNAME), user_input.get(CONF_PASSWORD)
                )
                is not True
            ):
                errors["base"] = "authorization_error"
                return await self._show_setup_form(errors)
        except aiohttp.ClientError:
            errors["base"] = "connection_error"
            return await self._show_setup_form(errors)

        return self.async_create_entry(
            title=client.account_id,
            data={
                CONF_USERNAME: user_input.get(CONF_USERNAME),
                CONF_PASSWORD: user_input.get(CONF_PASSWORD),
                CONF_ACCOUNT_ID: client.account_id,
            },
        )
