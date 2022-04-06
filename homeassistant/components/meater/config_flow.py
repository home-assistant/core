"""Config flow for Meater."""
from meater import AuthenticationError, MeaterApi, ServiceUnavailableError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN

FLOW_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class MeaterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Meater Config Flow."""

    async def async_step_user(self, user_input=None):
        """Define the login user step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=FLOW_SCHEMA,
            )

        username: str = user_input[CONF_USERNAME]
        await self.async_set_unique_id(username.lower())
        self._abort_if_unique_id_configured()

        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]

        session = aiohttp_client.async_get_clientsession(self.hass)

        api = MeaterApi(session)
        errors = {}

        try:
            await api.authenticate(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
        except AuthenticationError:
            errors["base"] = "invalid_auth"
        except ServiceUnavailableError:
            errors["base"] = "service_unavailable_error"
        except Exception:  # pylint: disable=broad-except
            errors["base"] = "unknown_auth_error"
        else:
            return self.async_create_entry(
                title="Meater",
                data={"username": username, "password": password},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=FLOW_SCHEMA,
            errors=errors,
        )
