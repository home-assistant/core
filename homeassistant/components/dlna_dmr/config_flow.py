"""Config flow for the DLNA DMR platform."""

import logging

from url_normalize import url_normalize
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_URL

from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


# TODO options flow for listen_ip, listen_port, callback_url_override


class ConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """DLNA DMR config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def _async_show_form(self, user_input=None, errors=None):
        if user_input is None:
            user_input = {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL, self.context.get(CONF_URL, "")): str,
                    vol.Optional(CONF_NAME, self.context.get(CONF_NAME, "")): str,
                }
            ),
            errors=errors or {},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if user_input is None:
            return await self._async_show_form()

        # Validate input
        user_input[CONF_URL] = self.context[CONF_URL] = url_normalize(
            user_input[CONF_URL], default_scheme="http"
        )
        if "://" not in user_input[CONF_URL]:
            return await self._async_show_form(
                user_input=user_input, errors={CONF_URL: "invalid_url"}
            )

        # Try to connect and get device name if one was not set, and unique id
        # TODO

        # Check if already configured
        if self._already_configured():
            return self.async_abort(reason="already_configured")

        # TODO await self.async_set_unique_id(TODO)
        # TODO self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=user_input.get(CONF_NAME), data=user_input,
        )

    async def async_step_import(self, user_input=None):
        """Import a config entry."""
        return await self.async_step_user(user_input=user_input)

    def _already_configured(self):
        """See if we already have a device matching user input configured."""
        return any(
            x[CONF_URL] == self.context[CONF_URL] for x in self._async_current_entries()
        )
