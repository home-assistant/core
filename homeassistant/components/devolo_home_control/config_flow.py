"""Config flow to configure the iCloud integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class DevoloHomeControlFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a iCloud config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize devolo Home Control flow."""
        pass

    async def _show_setup_form(self, errors=None):
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional("mPRM", default="https://mprm-test.devolo.net"): str,
                    vol.Optional(
                        "mydevolo", default="https://dcloud-test.devolo.net/"
                    ): str,
                }
            ),
            errors=errors or {},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return await self._show_setup_form(user_input)

        return self.async_create_entry(
            title="devolo Home Control",
            data={
                CONF_PASSWORD: user_input.get(CONF_PASSWORD),
                CONF_USERNAME: user_input.get(CONF_USERNAME),
                "mydevolo": user_input.get("mydevolo"),
                "mprm": user_input.get("mPRM"),
            },
        )
