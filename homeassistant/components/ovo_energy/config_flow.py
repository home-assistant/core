"""Config flow to configure the OVO Energy integration."""
import logging

import aiohttp
from ovoenergy.ovoenergy import OVOEnergy
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import CONF_ACCOUNT_ID, DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class OVOEnergyFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a OVO Energy config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is not None:
            client = OVOEnergy()
            try:
                authenticated = await client.authenticate(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except aiohttp.ClientError:
                errors["base"] = "connection_error"
            else:
                if authenticated:
                    await self.async_set_unique_id(user_input[CONF_USERNAME])
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=client.account_id,
                        data={
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            CONF_ACCOUNT_ID: client.account_id,
                        },
                    )

                errors["base"] = "authorization_error"

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )
