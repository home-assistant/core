"""Config flow to configure russound_rio component."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from russound_rio import Russound
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, RUSSOUND_RIO_EXCEPTIONS

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_PORT, default=9621): cv.port,
    },
    extra=vol.ALLOW_EXTRA,
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
            name = user_input[CONF_NAME]
            port = user_input[CONF_PORT]

            self.context[CONF_HOST] = host

            try:
                russ = Russound(self.hass.loop, host, port)
                async with asyncio.timeout(5):
                    await russ.connect()
                    await russ.enumerate_sources()
                    await russ.close()
            except RUSSOUND_RIO_EXCEPTIONS as err:
                _LOGGER.error("Could not connect to Russound RIO: %s", err)
                errors["base"] = "cannot_connect"
            else:
                data = {
                    CONF_HOST: host,
                    CONF_NAME: name,
                    CONF_PORT: port,
                }

                return self.async_create_entry(title=name, data=data)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> ConfigFlowResult:
        """Attempt to import the existing configuration."""
        self._async_abort_entries_match({CONF_HOST: import_config[CONF_HOST]})
        host = import_config[CONF_HOST]
        name = import_config[CONF_NAME]
        port = import_config.get(CONF_PORT, 9621)

        self.context[CONF_HOST] = host

        # Connection logic is repeated here since this method will be removed in future releases
        try:
            russ = Russound(self.hass.loop, host, port)
            async with asyncio.timeout(5):
                await russ.connect()
                await russ.enumerate_sources()
                await russ.close()
        except RUSSOUND_RIO_EXCEPTIONS as err:
            _LOGGER.error("Could not connect to Russound RIO: %s", err)
            return self.async_abort(
                reason="cannot_connect", description_placeholders={}
            )
        else:
            data = {
                CONF_HOST: host,
                CONF_NAME: name,
                CONF_PORT: port,
            }

            return self.async_create_entry(title=name, data=data)
