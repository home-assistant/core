"""Config flow to configure Goodwe inverters using their local API."""
from __future__ import annotations

import logging

from goodwe import InverterError, connect
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_MODEL_FAMILY, DEFAULT_NAME, DOMAIN

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)

_LOGGER = logging.getLogger(__name__)


class GoodweFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Goodwe config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST]

            try:
                inverter = await connect(host=host, retries=10)
            except InverterError:
                errors[CONF_HOST] = "connection_error"
            else:
                await self.async_set_unique_id(inverter.serial_number)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data={
                        CONF_HOST: host,
                        CONF_MODEL_FAMILY: type(inverter).__name__,
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )
