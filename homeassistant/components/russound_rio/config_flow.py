"""Config flow to configure russound_rio component."""

from __future__ import annotations

import logging
from typing import Any

from aiorussound import RussoundClient, RussoundTcpConnectionHandler
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, RUSSOUND_RIO_EXCEPTIONS

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
                await client.connect()
                controller = client.controllers[1]
                await client.disconnect()
            except RUSSOUND_RIO_EXCEPTIONS:
                _LOGGER.exception("Could not connect to Russound RIO")
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(controller.mac_address)
                if self.source == SOURCE_RECONFIGURE:
                    self._abort_if_unique_id_mismatch(reason="wrong_device")
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        data_updates=user_input,
                    )
                self._abort_if_unique_id_configured()
                data = {CONF_HOST: host, CONF_PORT: port}
                return self.async_create_entry(
                    title=controller.controller_type, data=data
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        if not user_input:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=DATA_SCHEMA,
            )
        return await self.async_step_user(user_input)
