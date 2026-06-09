"""Config flow for AquaLogic."""

import socket
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT): cv.port,
    }
)


def _can_connect(host: str, port: int) -> bool:
    """Test if we can connect to the AquaLogic device."""
    try:
        with socket.create_connection((host, port), timeout=5):
            return True
    except OSError:
        return False


class AquaLogicConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AquaLogic."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(user_input)

            if await self.hass.async_add_executor_job(
                _can_connect, user_input[CONF_HOST], user_input[CONF_PORT]
            ):
                return self.async_create_entry(title="AquaLogic", data=user_input)

            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import AquaLogic config from configuration.yaml."""
        self._async_abort_entries_match(
            {CONF_HOST: import_data[CONF_HOST], CONF_PORT: import_data[CONF_PORT]}
        )

        if not await self.hass.async_add_executor_job(
            _can_connect, import_data[CONF_HOST], import_data[CONF_PORT]
        ):
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(title="AquaLogic", data=import_data)
