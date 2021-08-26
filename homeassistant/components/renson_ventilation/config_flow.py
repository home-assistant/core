"""Configuration flow for Renson ventilation integration."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST

from .const import DOMAIN


class RensonConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Renson config flow."""

    async def async_step_user(self, user_input):
        """Handle a Renson config flow start."""
        # if user_input is not None:

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({vol.Required(CONF_HOST): str})
        )
