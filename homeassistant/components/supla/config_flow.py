"""Config flow to configure Supla component."""

import voluptuous as vol
from pysupla import SuplaAPI

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import callback
from homeassistant.util import slugify
import logging

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@callback
def configured_host(hass):
    """Return a set of the configured hosts."""
    return set(
        (slugify(entry.data[CONF_HOST]))
        for entry in hass.config_entries.async_entries(DOMAIN)
    )


@config_entries.HANDLERS.register(DOMAIN)
class SuplaFlowHandler(config_entries.ConfigFlow):
    """Supla config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize Supla configuration flow."""
        pass

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        # if self._async_current_entries():
        #     return self.async_abort(reason='single_instance_allowed')
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        if user_input is not None:
            return await self.async_step_init(user_input=None)
        return self.async_show_form(step_id="confirm", errors=errors)

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        if user_input is not None:
            _LOGGER.error(user_input[CONF_HOST])
            _LOGGER.error(user_input[CONF_TOKEN])
            # Test connection
            server = SuplaAPI(user_input[CONF_HOST], user_input[CONF_TOKEN])
            srv_info = server.get_server_info()
            if srv_info.get("authenticated"):
                """Finish config flow"""
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )
            else:
                _LOGGER.error(
                    "Server: %s not configured. API call returned: %s",
                    user_input[CONF_HOST],
                    srv_info,
                )
                errors = {CONF_HOST: "supla_no_connection"}

            """TEST Finish config flow"""
            return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOST): str, vol.Required(CONF_TOKEN): str}
            ),
            errors=errors,
        )
