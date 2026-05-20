"""Config flow to configure Dreo."""

from typing import Any

from pydreo import DreoBusinessException, DreoException
from pydreo.cloud.client import DreoClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class DreoFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Dreo config flow."""

    VERSION = 1

    async def _validate_login(self, username: str, password: str) -> str | None:
        """Validate login credentials."""
        client = DreoClient(username, password)

        try:
            await self.hass.async_add_executor_job(client.login)
        except DreoBusinessException:
            return "invalid_auth"
        except DreoException:
            return "cannot_connect"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()

            if not (error := await self._validate_login(username, password)):
                return self.async_create_entry(
                    title=username,
                    data={CONF_USERNAME: username, CONF_PASSWORD: password},
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
