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
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class DreoFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Dreo config flow."""

    VERSION = 1

    async def _validate_login(
        self, username: str, password: str
    ) -> tuple[bool, str | None]:
        """Validate login credentials."""
        client = DreoClient(username, password)

        try:
            await self.hass.async_add_executor_job(client.login)
        except DreoBusinessException:
            return False, "invalid_auth"
        except DreoException:
            return False, "cannot_connect"
        return True, None

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication flow start."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        username = reauth_entry.data[CONF_USERNAME]

        if user_input:
            password = user_input[CONF_PASSWORD]
            is_valid, error = await self._validate_login(username, password)
            if is_valid:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PASSWORD: password},
                )
            errors["base"] = error or "unknown"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
        )

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

            is_valid, error = await self._validate_login(username, password)
            if is_valid:
                return self.async_create_entry(
                    title=username,
                    data={CONF_USERNAME: username, CONF_PASSWORD: password},
                )
            errors["base"] = error or "unknown"
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
