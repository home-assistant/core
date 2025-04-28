"""config flow from hiportal home assistant integration."""

import voluptuous as vol

from homeassistant import config_entries

from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN


@config_entries.HANDLERS.register(DOMAIN)
class HiPortalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """config flow from hiportal home assistant integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Prompt the user for HiPortal credentials."""
        errors = {}

        if user_input is not None:
            # TODO: Validate credentials here if needed
            return self.async_create_entry(title="HiPortal Solar", data=user_input)

        data_schema = vol.Schema({
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        })

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)
