"""Config flow to configure emulated_roku component."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback

from .const import CONF_LISTEN_PORT, DEFAULT_NAME, DEFAULT_PORT, DOMAIN


@callback
def configured_servers(hass):
    """Return a set of the configured servers."""
    return set(
        entry.data[CONF_NAME] for entry in hass.config_entries.async_entries(DOMAIN)
    )


@config_entries.HANDLERS.register(DOMAIN)
class EmulatedRokuFlowHandler(config_entries.ConfigFlow):
    """Handle an emulated_roku config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            name = user_input[CONF_NAME]

            if name in configured_servers(self.hass):
                return self.async_abort(reason="name_exists")

            return self.async_create_entry(title=name, data=user_input)

        servers_num = len(configured_servers(self.hass))

        if servers_num:
            default_name = f"{DEFAULT_NAME} {servers_num + 1}"
            default_port = DEFAULT_PORT + servers_num
        else:
            default_name = DEFAULT_NAME
            default_port = DEFAULT_PORT

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=default_name): str,
                    vol.Required(CONF_LISTEN_PORT, default=default_port): vol.Coerce(
                        int
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_config):
        """Handle a flow import."""
        return await self.async_step_user(import_config)
