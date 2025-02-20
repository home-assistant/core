"""Config flow for Satel Integra."""

from __future__ import annotations

from copy import deepcopy
import logging
from typing import Any

from satel_integra.satel_integra import AsyncSatel
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_CODE, CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import DEFAULT_PORT, DOMAIN, SatelConfigEntry

_LOGGER = logging.getLogger(__package__)

CONF_ACTION_NUMBER = "number"
CONF_ACTION = "action"

ACTION_EDIT = "edit"
ACTION_ADD = "add"
ACTION_DELETE = "delete"

CONNECTION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_CODE): cv.string,
    }
)

CODE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_CODE): cv.string,
    }
)


class SatelConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Satel Integra config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: SatelConfigEntry,
    ) -> SatelOptionsFlow:
        """Create the options flow."""
        return SatelOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            valid = await self.test_connection(
                user_input[CONF_HOST], user_input.get(CONF_PORT, DEFAULT_PORT)
            )

            if valid:
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                    },
                    options={CONF_CODE: user_input.get(CONF_CODE)},
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


class SatelOptionsFlow(OptionsFlow):
    """Handle Satel options flow."""

    def __init__(self, config_entry: SatelConfigEntry) -> None:
        """Initialize Satel options."""
        self.options = deepcopy(dict(config_entry.options))

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Init step."""
        return self.async_show_menu(
            step_id="init", menu_options=["general", "partitions"]
        )

    async def async_step_general(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """General step."""
        if user_input is not None:
            return self.async_create_entry(
                data={**self.options, CONF_CODE: user_input.get(CONF_CODE)}
            )

        return self.async_show_form(
            step_id="general",
            data_schema=self.add_suggested_values_to_schema(
                CODE_SCHEMA, self.options.get(CONF_CODE)
            ),
        )
