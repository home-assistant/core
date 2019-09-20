"""Config flow to configure Livebox."""
from collections import namedtuple

from aiosysbus.exceptions import AuthorizationError

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD


from . import LiveboxData
from .const import DOMAIN, DEFAULT_USERNAME, DEFAULT_HOST, DEFAULT_PORT, TEMPLATE_SENSOR


class LiveboxFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Livebox config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the Livebox flow."""

        self._box = None
        self.host = None
        self.port = None
        self.username = None
        self.password = None
        self.box_id = None

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""

        errors = {}
        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): str,
                vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        if user_input is not None:
            self.host = user_input["host"]
            self.port = user_input["port"]
            self.username = user_input["username"]
            self.password = user_input["password"]

            try:
                user_entry = namedtuple("user_entry", "data")
                entry = user_entry(user_input)
                self._box = LiveboxData(entry)

                if await self._box.async_conn():
                    return await self.async_step_register()

            except AuthorizationError:
                errors["base"] = "login_inccorect"

            except Exception:
                errors["base"] = "linking"

        # If there was no user input, do not show the errors.
        if user_input is None:
            errors = {}

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_register(self, user_input=None):
        """Step for register component."""

        errors = {}
        self.box_id = (await self._box.async_infos())["SerialNumber"]
        entry_id = self.hass.config_entries.async_entries(DOMAIN)
        if self.box_id:
            if entry_id and entry_id.get("data", {}).get("id", 0) == self.box_id:
                self.hass.config_entries.async_remove(entry_id)
            return self.async_create_entry(
                title=f"{TEMPLATE_SENSOR}",
                data={
                    "id": self.box_id,
                    "host": self.host,
                    "port": self.port,
                    "username": self.username,
                    "password": self.password,
                },
            )
        else:
            errors["base"] = "register_failed"

        return self.async_show_form(step_id="register", errors=errors)
