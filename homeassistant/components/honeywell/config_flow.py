"""Config flow to configure the honeywell integration."""
import somecomfort
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import (
    CONF_COOL_AWAY_TEMPERATURE,
    CONF_DEV_ID,
    CONF_HEAT_AWAY_TEMPERATURE,
    CONF_LOC_ID,
    DEFAULT_COOL_AWAY_TEMPERATURE,
    DEFAULT_HEAT_AWAY_TEMPERATURE,
    DOMAIN,
)


class HoneywellConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a honeywell config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Show the setup form to the user."""
        data_schema = {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(
                CONF_COOL_AWAY_TEMPERATURE, default=DEFAULT_COOL_AWAY_TEMPERATURE
            ): vol.Coerce(int),
            vol.Optional(
                CONF_HEAT_AWAY_TEMPERATURE, default=DEFAULT_HEAT_AWAY_TEMPERATURE
            ): vol.Coerce(int),
            vol.Optional(CONF_DEV_ID): str,
            vol.Optional(CONF_LOC_ID): str,
        }

        errors = {}

        if user_input is not None:
            valid = await self.is_valid(user_input)
            if valid:
                return self.async_create_entry(
                    title=DOMAIN,
                    data=user_input,
                )

            errors["base"] = "auth_error"

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors=errors
        )

    async def is_valid(self, user_input) -> bool:
        """Check if login credentials are valid."""
        try:
            await self.hass.async_add_executor_job(
                somecomfort.SomeComfort, user_input["username"], user_input["password"]
            )
            return True
        except somecomfort.SomeComfortError:
            return False
