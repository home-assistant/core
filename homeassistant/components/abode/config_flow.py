"""Config flow for the Abode Security System component."""
from collections import OrderedDict
import voluptuous as vol

from abodepy.exceptions import AbodeAuthenticationException
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from .const import DOMAIN


@callback
def configured_instances(hass):
    """Return a set of configured Abode instances."""
    return set(
        entry.data[CONF_USERNAME] for entry in hass.config_entries.async_entries(DOMAIN)
    )


@config_entries.HANDLERS.register(DOMAIN)
class AbodeFlowHandler(config_entries.ConfigFlow):
    """Config flow for Abode."""

    VERSION = 1

    def __init__(self):
        """Initialize."""
        self.data_schema = OrderedDict()
        self.data_schema[vol.Required(CONF_USERNAME)] = str
        self.data_schema[vol.Required(CONF_PASSWORD)] = str

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        from abodepy import Abode

        if not user_input:
            return await self._show_form()

        if user_input[CONF_USERNAME] in configured_instances(self.hass):
            return await self._show_form({CONF_USERNAME: "identifier_exists"})

        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]

        try:
            Abode(username, password, auto_login=True)

        # Need to add error checking if Abode server is down/not responding
        except AbodeAuthenticationException:
            return await self._show_form({"base": "invalid_credentials"})

        return self.async_create_entry(
            title=user_input[CONF_USERNAME],
            data={CONF_USERNAME: username, CONF_PASSWORD: password},
        )

    async def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(self.data_schema),
            errors=errors if errors else {},
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        if import_config[CONF_USERNAME] in configured_instances(self.hass):
            return await self._show_form({CONF_USERNAME: "identifier_exists"})

        return self.async_create_entry(
            title=import_config["username"], data=import_config
        )
