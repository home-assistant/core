"""Config flow for Waze Travel Time integration."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.util import slugify

from .const import CONF_DESTINATION, CONF_ORIGIN, DEFAULT_NAME, DOMAIN, WAZE_SCHEMA


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Waze Travel Time."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            await self.async_set_unique_id(
                slugify(
                    f"{DOMAIN}_{user_input[CONF_ORIGIN]}_{user_input[CONF_DESTINATION]}"
                )
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input.get(
                    CONF_NAME,
                    (
                        f"{DEFAULT_NAME}: {user_input[CONF_ORIGIN]} -> "
                        f"{user_input[CONF_DESTINATION]}"
                    ),
                ),
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(WAZE_SCHEMA),
        )

    async_step_import = async_step_user
