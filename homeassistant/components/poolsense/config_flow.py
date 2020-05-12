"""Config flow for PoolSense integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


class PoolSenseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PoolSense."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    _options = None

    def __init__(self):
        """Initialize iCloud config flow."""
        self.token = None
        self._email = None
        self._password = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self._email = user_input[CONF_EMAIL]
            self._password = user_input[CONF_PASSWORD]
            _LOGGER.info("*******HAEMISH*******: " + self._email + ":" + self._password)

            return self.async_create_entry(
                title=self._email,
                data={
                    CONF_EMAIL: self._email,
                    CONF_PASSWORD: self._password,
                    "TOKEN": self.token,
                },
            )
        else:
            return await self._show_setup_form(user_input, errors)

    async def _show_setup_form(self, user_input=None, errors=None):
        """Show the setup form to the user."""

        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_EMAIL, default=user_input.get(CONF_EMAIL, "")
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                    ): str,
                    vol.Optional(
                        "serial", default=user_input.get("Serial Number", "")
                    ): str,
                }
            ),
            errors=errors or {},
        )
