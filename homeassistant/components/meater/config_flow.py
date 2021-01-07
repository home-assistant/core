"""Config flow for Meater."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN


class MeaterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Meater Config Flow."""

    async def async_step_user(self, user_input=None):
        """Define the login user step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
                ),
            )

        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]

        return self.async_create_entry(
            title="Meater Integration Entry",
            data={"username": username, "password": password},
        )
