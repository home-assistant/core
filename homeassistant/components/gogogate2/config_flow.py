"""Config flow for Gogogate2."""
import logging
import re

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_USERNAME

from .common import async_api_info_or_none, get_api
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class Gogogate2FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Gogogate2 config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_import(self, config_data: dict = None):
        """Handle importing of configuration."""
        return await self.async_step_finish(config_data)

    async def async_step_user(self, user_input: dict = None):
        """Handle user initiated flow."""
        if user_input is not None:
            return await self.async_step_finish(user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_IP_ADDRESS): str,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
        )

    async def async_step_finish(self, user_input: dict):
        """Validate and create config entry."""

        api = get_api(user_input)
        data = await async_api_info_or_none(self.hass, api)
        if data is None:
            return self.async_abort(
                reason="cannot_connect",
                description_placeholders={CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS]},
            )

        await self.async_set_unique_id(re.sub("\\..*$", "", data.remoteaccess))
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=data.gogogatename, data=user_input)
