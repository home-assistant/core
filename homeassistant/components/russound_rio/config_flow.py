"""Config flow to configure russound_rio component."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiorussound import RussoundClient, RussoundTcpConnectionHandler
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import config_validation as cv

from .const import CONNECT_TIMEOUT, DOMAIN, RUSSOUND_RIO_EXCEPTIONS

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=9621): cv.port,
    }
)

_LOGGER = logging.getLogger(__name__)


class FlowHandler(ConfigFlow, domain=DOMAIN):
    """Russound RIO configuration flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            client = RussoundClient(RussoundTcpConnectionHandler(host, port))
            try:
                async with asyncio.timeout(CONNECT_TIMEOUT):
                    await client.connect()
                    controller = client.controllers[1]
                    await client.disconnect()
            except RUSSOUND_RIO_EXCEPTIONS:
                _LOGGER.exception("Could not connect to Russound RIO")
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(controller.mac_address)
                self._abort_if_unique_id_configured()
                data = {CONF_HOST: host, CONF_PORT: port}
                return self.async_create_entry(
                    title=controller.controller_type, data=data
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Attempt to import the existing configuration."""
        self._async_abort_entries_match({CONF_HOST: import_data[CONF_HOST]})
        host = import_data[CONF_HOST]
        port = import_data.get(CONF_PORT, 9621)

        # Connection logic is repeated here since this method will be removed in future releases
        client = RussoundClient(RussoundTcpConnectionHandler(host, port))
        try:
            async with asyncio.timeout(CONNECT_TIMEOUT):
                await client.connect()
                controller = client.controllers[1]
                await client.disconnect()
        except RUSSOUND_RIO_EXCEPTIONS:
            _LOGGER.exception("Could not connect to Russound RIO")
            return self.async_abort(
                reason="cannot_connect", description_placeholders={}
            )
        else:
            await self.async_set_unique_id(controller.mac_address)
            self._abort_if_unique_id_configured()
            data = {CONF_HOST: host, CONF_PORT: port}
            return self.async_create_entry(title=controller.controller_type, data=data)
