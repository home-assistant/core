"""Config flow to configure the SmartTub integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .const import DOMAIN  # pylint: disable=unused-import
from .controller import SmartTubController

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
)


_LOGGER = logging.getLogger(__name__)


class SmartTubConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """SmartTub configuration flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            controller = SmartTubController(self.hass)
            account = await controller.login(
                user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
            if account is not None:
                await self.async_set_unique_id(account.id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_EMAIL], data=user_input
                )

            errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, user_input=None):
        """Handle a flow initiated by failed auth."""
        return await self.async_step_user(user_input)
