"""Config flow to configure emulated_roku component."""

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.core import callback

from .const import CONF_LISTEN_PORT, DEFAULT_NAME, DEFAULT_PORT, DOMAIN


@callback
def configured_servers(hass):
    """Return a set of the configured servers."""
    return {
        entry.data[CONF_NAME] for entry in hass.config_entries.async_entries(DOMAIN)
    }


class EmulatedRokuFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle an emulated_roku config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_NAME: user_input[CONF_NAME]})
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

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

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle a flow import."""
        return await self.async_step_user(import_data)
