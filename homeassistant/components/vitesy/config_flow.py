"""Config flow for the Vitesy integration."""

from typing import Any, override

from aiovitesy.api import VitesyApi
from aiovitesy.exceptions import CannotAuthenticate, VitesyError
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_EMAIL): str,
        probatio.Required(CONF_PASSWORD): str,
    }
)


async def _validate_credentials(hass: HomeAssistant, email: str, password: str) -> str:
    """Authenticate and return the account's stable user id."""
    api = VitesyApi(email, password, async_get_clientsession(hass))
    await api.login()
    user = await api.get_user()
    user_id = user.get("id")
    if not isinstance(user_id, (str, int)):
        raise VitesyError(f"Profile response is missing a valid user id: {user_id!r}")
    return str(user_id)


class VitesyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Vitesy."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL]

            try:
                user_id = await _validate_credentials(
                    self.hass, email, user_input[CONF_PASSWORD]
                )
            except CannotAuthenticate:
                errors["base"] = "invalid_auth"
            except VitesyError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=email, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
