"""Config flow utilities."""

from collections.abc import Mapping
from typing import Any

from pyvesync import VeSync
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


class VeSyncFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    MINOR_VERSION = 2

    @callback
    def _show_form(self, errors: dict[str, str] | None = None) -> ConfigFlowResult:
        """Show form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors if errors else {},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow start."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if not user_input:
            return self._show_form()

        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]

        manager = VeSync(username, password)
        login = await self.hass.async_add_executor_job(manager.login)
        if not login:
            return self._show_form(errors={"base": "invalid_auth"})

        return self.async_create_entry(
            title=username,
            data={CONF_USERNAME: username, CONF_PASSWORD: password},
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication with vesync."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication with vesync."""

        if user_input:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            manager = VeSync(username, password)
            login = await self.hass.async_add_executor_job(manager.login)
            if login:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=DATA_SCHEMA,
            description_placeholders={"name": "VeSync"},
            errors={"base": "invalid_auth"},
        )
