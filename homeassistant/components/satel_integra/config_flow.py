"""Config flow for Satel Integra."""

from __future__ import annotations

from satel_integra.satel_integra import AsyncSatel
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_CODE, CONF_HOST, CONF_PORT
from homeassistant.helpers import config_validation as cv

from .const import DEFAULT_PORT, DOMAIN

CONNECTION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_CODE): cv.string,
    }
)


class SatelConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Satel Integra config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            valid = await self.test_connection(
                user_input[CONF_HOST], user_input.get(CONF_PORT, DEFAULT_PORT)
            )

            if valid:
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=CONNECTION_SCHEMA, errors=errors
        )

    async def test_connection(self, host, port) -> bool:
        """Test a connection to the Satel alarm."""
        controller = AsyncSatel(host, port, self.hass.loop)

        result = await controller.connect()

        # Make sure we close the connection again
        controller.close()

        return result
