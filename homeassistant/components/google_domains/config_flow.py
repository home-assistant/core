"""Config flow for Google Domains."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_DOMAIN, CONF_PASSWORD, CONF_USERNAME

from .consts import DOMAIN  # pylint: disable=unused-import

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DOMAIN): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class GoogleDomainsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Google Domains Config Flow."""

    async def async_step_user(self, user_input=None):
        """Config flow user step."""
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_DOMAIN], data=user_input
            )

        return self.async_show_form(step_id="user", data_schema=CONFIG_SCHEMA)
