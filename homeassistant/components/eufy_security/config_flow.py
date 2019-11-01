"""Define a config flow to configure the Eufy Security integration."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN


@callback
def configured_instances(hass):
    """Return a set of configured Eufy Security instances."""
    return set(
        entry.data[CONF_USERNAME] for entry in hass.config_entries.async_entries(DOMAIN)
    )


@config_entries.HANDLERS.register(DOMAIN)
class EufySecurityFlowHandler(config_entries.ConfigFlow):
    """Handle a Eufy Security config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def _show_form(self, errors=None):
        """Show the form to the user."""
        data_schema = vol.Schema(
            {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors or {}
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        from eufy_security import async_login
        from eufy_security.errors import InvalidCredentialsError

        if not user_input:
            return await self._show_form()

        if user_input[CONF_USERNAME] in configured_instances(self.hass):
            return await self._show_form({CONF_USERNAME: "identifier_exists"})

        session = aiohttp_client.async_get_clientsession(self.hass)

        try:
            await async_login(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD], session
            )
        except InvalidCredentialsError:
            return await self._show_form({"base": "invalid_credentials"})

        return self.async_create_entry(title=user_input[CONF_USERNAME], data=user_input)
