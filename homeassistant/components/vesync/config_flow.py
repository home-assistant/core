"""Config flow utilities."""

from typing import Any

from pyvesync import VeSync
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


class VesyncOptionFlowHandler(OptionsFlow):
    """Handle an option flow for Vesync."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize option flow instance."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the vesync options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=self.config_entry.options.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                ),
            ): int,
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))


class VeSyncFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> VesyncOptionFlowHandler:
        """Get the options flow for this handler."""
        return VesyncOptionFlowHandler(config_entry)

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
