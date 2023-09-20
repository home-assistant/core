"""Config flow for Ecoforest integration."""
from __future__ import annotations

import logging
from typing import Any

from httpx import BasicAuth
from pyecoforest.api import EcoforestApi
from pyecoforest.exceptions import EcoforestAuthenticationRequired
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ecoforest."""

    VERSION = 1

    @callback
    def _async_current_hosts(self) -> set[str]:
        """Return a set of hosts."""
        return {
            entry.data[CONF_HOST]
            for entry in self._async_current_entries(include_ignore=False)
            if CONF_HOST in entry.data
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        host = (user_input or {}).get(CONF_HOST) or ""

        if user_input is not None:
            if host in self._async_current_hosts():
                return self.async_abort(reason="already_configured")

            try:
                api = EcoforestApi(
                    user_input[CONF_HOST],
                    BasicAuth(user_input[CONF_USERNAME], user_input[CONF_PASSWORD]),
                )
                device = await api.get()
            except EcoforestAuthenticationRequired:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "cannot_connect"
            else:
                if not self.unique_id:
                    await self.async_set_unique_id(device.serial_number)
                    name = (
                        f"{MANUFACTURER} {self.unique_id}"
                        if self.unique_id
                        else MANUFACTURER
                    )
                return self.async_create_entry(
                    title=name, data={CONF_HOST: host} | user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
