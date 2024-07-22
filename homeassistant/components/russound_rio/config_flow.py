"""Config flow to configure russound_rio component."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiorussound import Controller, Russound
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import config_validation as cv

from .const import (
    CONNECT_TIMEOUT,
    DOMAIN,
    RUSSOUND_RIO_EXCEPTIONS,
    NoPrimaryControllerException,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=9621): cv.port,
    }
)

_LOGGER = logging.getLogger(__name__)


def find_primary_controller_metadata(
    controllers: dict[int, Controller],
) -> tuple[str, str]:
    """Find the mac address of the primary Russound controller."""
    if 1 in controllers:
        c = controllers[1]
        return c.mac_address, c.controller_type
    raise NoPrimaryControllerException


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

            controllers = None
            russ = Russound(self.hass.loop, host, port)
            try:
                async with asyncio.timeout(CONNECT_TIMEOUT):
                    await russ.connect()
                    controllers = await russ.enumerate_controllers()
                    metadata = find_primary_controller_metadata(controllers)
                    await russ.close()
            except RUSSOUND_RIO_EXCEPTIONS:
                _LOGGER.exception("Could not connect to Russound RIO")
                errors["base"] = "cannot_connect"
            except NoPrimaryControllerException:
                _LOGGER.exception(
                    "Russound RIO device doesn't have a primary controller",
                )
                errors["base"] = "no_primary_controller"
            else:
                await self.async_set_unique_id(metadata[0])
                self._abort_if_unique_id_configured()
                data = {CONF_HOST: host, CONF_PORT: port}
                return self.async_create_entry(title=metadata[1], data=data)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> ConfigFlowResult:
        """Attempt to import the existing configuration."""
        self._async_abort_entries_match({CONF_HOST: import_config[CONF_HOST]})
        host = import_config[CONF_HOST]
        port = import_config.get(CONF_PORT, 9621)

        # Connection logic is repeated here since this method will be removed in future releases
        russ = Russound(self.hass.loop, host, port)
        try:
            async with asyncio.timeout(CONNECT_TIMEOUT):
                await russ.connect()
                controllers = await russ.enumerate_controllers()
                metadata = find_primary_controller_metadata(controllers)
                await russ.close()
        except RUSSOUND_RIO_EXCEPTIONS:
            _LOGGER.exception("Could not connect to Russound RIO")
            return self.async_abort(
                reason="cannot_connect", description_placeholders={}
            )
        except NoPrimaryControllerException:
            _LOGGER.exception("Russound RIO device doesn't have a primary controller")
            return self.async_abort(
                reason="no_primary_controller", description_placeholders={}
            )
        else:
            await self.async_set_unique_id(metadata[0])
            self._abort_if_unique_id_configured()
            data = {CONF_HOST: host, CONF_PORT: port}
            return self.async_create_entry(title=metadata[1], data=data)
