"""Config flow for FireServiceRota."""
from pyfireservicerota import FireServiceRota, InvalidAuthError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_URL, CONF_USERNAME

from .const import DOMAIN, URL_LIST  # pylint: disable=unused-import

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default="www.brandweerrooster.nl"): vol.In(URL_LIST),
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class FireServiceRotaFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a FireServiceRota config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
            self._abort_if_unique_id_configured()

            try:
                api = FireServiceRota(
                    base_url=f"https://{user_input[CONF_URL]}",
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                )
                token_info = await self.hass.async_add_executor_job(api.request_tokens)

            except InvalidAuthError:
                return self.async_show_form(
                    step_id="user",
                    data_schema=DATA_SCHEMA,
                    errors={"base": "invalid_auth"},
                )

            return self.async_create_entry(
                title=user_input[CONF_USERNAME],
                data={
                    "auth_implementation": DOMAIN,
                    CONF_URL: user_input[CONF_URL],
                    CONF_TOKEN: token_info,
                },
            )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
