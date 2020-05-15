"""Config flow to configure the Smappee components."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_PASSWORD,
    CONF_PLATFORM,
    CONF_USERNAME,
)
from homeassistant.core import callback

from . import DOMAIN


@callback
def configured_instances(hass):
    """Return a set of configured Smappee instances."""
    return {
        entry.data[CONF_USERNAME] for entry in hass.config_entries.async_entries(DOMAIN)
    }


@config_entries.HANDLERS.register(DOMAIN)
class SmappeeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Smappee config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Config flow constructor."""
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        from pysmappee import Smappee

        if not user_input:
            return await self._show_config_form()

        if user_input[CONF_USERNAME] in configured_instances(self.hass):
            return await self._show_config_form(
                errors={CONF_USERNAME: "identifier_exists"}
            )

        username = user_input.get(CONF_USERNAME)
        password = user_input.get(CONF_PASSWORD)
        client_id = user_input.get(CONF_CLIENT_ID)
        client_secret = user_input.get(CONF_CLIENT_SECRET)
        platform = user_input.get(CONF_PLATFORM)

        try:
            await self.hass.async_add_executor_job(
                Smappee, username, password, client_id, client_secret, platform
            )
        except Exception:
            return await self._show_config_form(errors={"base": "invalid_credentials"})

        return self.async_create_entry(
            title=user_input[CONF_USERNAME], data=user_input,
        )

    async def _show_config_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_CLIENT_ID): str,
                    vol.Required(CONF_CLIENT_SECRET): str,
                    vol.Required(CONF_PLATFORM, default="PRODUCTION"): vol.In(
                        ["PRODUCTION", "ACCEPTANCE", "DEVELOPMENT"]
                    ),
                }
            ),
            errors=errors if errors else {},
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(user_input=import_config)
