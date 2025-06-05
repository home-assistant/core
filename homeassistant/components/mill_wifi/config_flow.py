"""Config flow for the Mill WiFi Official integration."""

from homeassistant import config_entries

from .api import MillApiClient
from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN


class MillConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow class."""

    async def async_step_user(self, user_input=None):
        """Initialize config flow."""
        if user_input is not None:
            api = MillApiClient(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
            await api.async_setup()
            try:
                await api.login()
            except Exception:  # noqa: BLE001
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._get_schema(),
                    errors={"base": "invalid_auth"},
                )

            return self.async_create_entry(title="Mill WiFi", data=user_input)

        return self.async_show_form(step_id="user", data_schema=self._get_schema())

    def _get_schema(self):
        import voluptuous as vol

        return vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
