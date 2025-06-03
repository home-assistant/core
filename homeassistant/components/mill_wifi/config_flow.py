"""Config flow for the Mill WiFi Official integration."""

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD
from .api import MillApiClient

class MillConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        if user_input is not None:
            api = MillApiClient(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
            await api.async_setup()
            try:
                await api.login()
            except Exception:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._get_schema(),
                    errors={"base": "invalid_auth"},
                )

            return self.async_create_entry(title="Mill WiFi", data=user_input)

        return self.async_show_form(step_id="user", data_schema=self._get_schema())

    def _get_schema(self):
        from homeassistant.helpers import config_validation as cv
        import voluptuous as vol
        return vol.Schema({
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        })
