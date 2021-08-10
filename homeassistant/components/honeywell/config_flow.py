"""Config flow to configure the honeywell integration."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.honeywell import get_somecomfort_client
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import CONF_COOL_AWAY_TEMPERATURE, CONF_HEAT_AWAY_TEMPERATURE, DOMAIN


class HoneywellConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a honeywell config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Create config entry. Show the setup form to the user."""
        errors = {}

        if user_input is not None:
            valid = await self.is_valid(**user_input)
            if valid:
                return self.async_create_entry(
                    title=DOMAIN,
                    data=user_input,
                )

            errors["base"] = "invalid_auth"

        data_schema = {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        }
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors=errors
        )

    async def is_valid(self, **kwargs) -> bool:
        """Check if login credentials are valid."""
        client = await self.hass.async_add_executor_job(
            get_somecomfort_client, kwargs[CONF_USERNAME], kwargs[CONF_PASSWORD]
        )

        return client is not None

    async def async_step_import(self, import_data):
        """Import entry from configuration.yaml."""
        return await self.async_step_user(
            {
                CONF_USERNAME: import_data[CONF_USERNAME],
                CONF_PASSWORD: import_data[CONF_PASSWORD],
                CONF_COOL_AWAY_TEMPERATURE: import_data[CONF_COOL_AWAY_TEMPERATURE],
                CONF_HEAT_AWAY_TEMPERATURE: import_data[CONF_HEAT_AWAY_TEMPERATURE],
            }
        )
