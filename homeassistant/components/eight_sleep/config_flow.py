"""Config flow for Eight Sleep integration."""
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import CONF_PARTNER, DEFAULT_PARTNER, DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Eight Sleep."""

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME])

            return self.async_create_entry(title="Eight Sleep", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_PARTNER, default=DEFAULT_PARTNER): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, user_input):
        """Handle import."""
        return await self.async_step_user(user_input)


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
