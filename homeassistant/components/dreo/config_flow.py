"""Config flow to configure Dreo."""

from collections.abc import Mapping
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

    async def _validate_login(
        self, username: str, password: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Validate login credentials."""
        client = DreoClient(username, password)

        try:
            auth_data = await self.hass.async_add_executor_job(client.login)
        except DreoBusinessException:
            return None, "invalid_auth"
        except DreoException:
            return None, "cannot_connect"
        return dict(auth_data) if isinstance(auth_data, Mapping) else {}, None

    @staticmethod
    def _get_unique_id(username: str, auth_data: dict[str, Any]) -> str:
        """Return the best available unique id for the account."""
        for key in ("user_id", "userId", "uid", "id"):
            value = auth_data.get(key)
            if value is not None:
                return str(value)
        return username.lower()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            auth_data, error = await self._validate_login(username, password)
            if auth_data is not None:
                await self.async_set_unique_id(
                    self._get_unique_id(username, auth_data)
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=username,
                    data={CONF_USERNAME: username, CONF_PASSWORD: password},
                )
            assert error is not None
            errors["base"] = error
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
