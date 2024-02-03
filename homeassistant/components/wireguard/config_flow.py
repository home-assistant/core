"""Config flow for WireGuard integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult

from .api import WireGuardAPI, WireGuardError
from .const import DEFAULT_HOST, DEFAULT_NAME, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
    }
)


class WireGuardConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WireGuard."""

    VERSION = 1

    host: str
    wireguard: WireGuardAPI

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.host = user_input[CONF_HOST]
            self.wireguard = WireGuardAPI(self.host)

            try:
                await self.hass.async_add_executor_job(self.wireguard.get_status)
            except WireGuardError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
