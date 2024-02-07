"""Config flow for WireGuard integration."""
from __future__ import annotations

from ha_wireguard_api import WireguardApiClient
from ha_wireguard_api.exceptions import (
    WireGuardInvalidJson,
    WireGuardResponseError,
    WireGuardTimeoutError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult

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
    wireguard: WireguardApiClient

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.host = user_input[CONF_HOST]
            self.wireguard = WireguardApiClient(self.host)

            try:
                await self.wireguard.get_peers()
                await self.wireguard.close()
            except WireGuardTimeoutError:
                errors["base"] = "timeout_connect"
            except WireGuardResponseError:
                errors["base"] = "cannot_connect"
            except WireGuardInvalidJson:
                errors["base"] = "invalid_response"
            else:
                return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
