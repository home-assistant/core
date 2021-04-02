"""Config flow for Meater."""
from meater import MeaterApi, AuthenticationError, ServiceUnavailableError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import aiohttp_client

# pylint: disable=unused-import
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

        await self.async_set_unique_id(user_input[CONF_USERNAME])
        self._abort_if_unique_id_configured()

        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]

        session = aiohttp_client.async_get_clientsession(self.hass)

        api = MeaterApi(session)

        try:
            await api.authenticate(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
        except AuthenticationError:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
                ),
                errors={"base": "invalid_auth"},
            )
        except ServiceUnavailableError:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
                ),
                errors={"base": "service_unavailable_error"},
            )
        except Exception:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
                ),
                errors={"base": "unknown_auth_error"},
            )

        return self.async_create_entry(
            title="Meater Integration Entry",
            data={"username": username, "password": password},
        )
