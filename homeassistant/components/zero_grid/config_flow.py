import voluptuous as vol

from homeassistant import config_entries

from .const import DOMAIN


class ZeroGridConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Zero Grid."""

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title="Zero Grid",
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required("name", default="Zero Grid"): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)
