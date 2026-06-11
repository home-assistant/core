"""Config flow for the Helty Flow integration."""

from typing import Any

from pyhelty import HeltyClient, HeltyConnectionError, HeltyError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


class HeltyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Helty Flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            client = HeltyClient(user_input[CONF_HOST])
            try:
                name = await client.async_get_name()
            except HeltyConnectionError:
                errors["base"] = "cannot_connect"
            except HeltyError:
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=name or user_input[CONF_HOST], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
