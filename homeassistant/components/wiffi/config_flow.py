"""Config flow for wiffi component.

Used by UI to setup a wiffi integration.
"""
import errno

import voluptuous as vol
from wiffi import WiffiTcpServer

from homeassistant import config_entries
from homeassistant.const import CONF_PORT
from homeassistant.core import callback

from .const import DEFAULT_PORT, DOMAIN  # pylint: disable=unused-import


class WiffiFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Wiffi server setup config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow.

        Called after wiffi integration has been selected in the 'add integration
        UI'. The user_input is set to None in this case. We will open a config
        flow form then.
        This function is also called if the form has been submitted. user_input
        contains a dict with the user entered values then.
        """
        if user_input is None:
            return self._async_show_form()

        # received input from form or configuration.yaml

        try:
            # try to start server to check whether port is in use
            server = WiffiTcpServer(user_input[CONF_PORT])
            await server.start_server()
            await server.close_server()
            return self.async_create_entry(
                title=f"Port {user_input[CONF_PORT]}", data=user_input
            )
        except OSError as exc:
            if exc.errno == errno.EADDRINUSE:
                return self.async_abort(reason="addr_in_use")
            return self.async_abort(reason="start_server_failed")

    @callback
    def _async_show_form(self, errors=None):
        """Show the config flow form to the user."""
        data_schema = {vol.Required(CONF_PORT, default=DEFAULT_PORT): int}

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors=errors or {}
        )
