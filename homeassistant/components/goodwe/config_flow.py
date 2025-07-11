"""Config flow to configure Goodwe inverters using their local API."""

from __future__ import annotations

import logging
from typing import Any

from goodwe import InverterError, connect
from goodwe.const import GOODWE_TCP_PORT, GOODWE_UDP_PORT
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import CONF_MODEL_FAMILY, DEFAULT_NAME, DOMAIN

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)

_LOGGER = logging.getLogger(__name__)


class GoodweFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Goodwe config flow."""

    VERSION = 1

    async def async_handle_successful_connection(self, inverter, host, port):
        """Handle a successful connection storing it's values on the entry data.

        Parameters:
        ----------
        inverter : Inverter
            Inverter object for the connection.
        host : str
            Host address for the connection with the Inverter.
        port : number
            Port number for the connection with the Inverter.
        """
        await self.async_set_unique_id(inverter.serial_number)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=DEFAULT_NAME,
            data={
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_MODEL_FAMILY: type(inverter).__name__,
            },
        )

    async def async_detect_inverter_port(self, host: str):
        """Detects the port of the Inverter.

        Parameters:
        ----------
        host : str
            Host address for the connection with the Inverter.

        Raises:
        ------
        InverterError
            If no inverter is found or not compatible
        """
        port = GOODWE_UDP_PORT
        try:
            inverter = await connect(host=host, port=port, retries=10)
        except InverterError:
            port = GOODWE_TCP_PORT
            inverter = await connect(host=host, port=port, retries=10)
        return inverter, port

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                inverter, port = await self.async_detect_inverter_port(host=host)
            except InverterError:
                errors[CONF_HOST] = "connection_error"
            else:
                return await self.async_handle_successful_connection(
                    inverter, host, port
                )
        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )
