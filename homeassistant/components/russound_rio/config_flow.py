"""Config flow to configure russound_rio component."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from russound_rio import Russound
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
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

    def __init__(self) -> None:
        """Initialize workflow."""
        self._host: str = ""
        self._name: str = ""
        self._port: int = 9621

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors=errors
            )

        self._host = user_input[CONF_HOST]
        self._name = user_input[CONF_NAME]
        self._port = user_input[CONF_PORT]
        return await self.async_step_pairing()

    async def async_step_pairing(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Display pairing form."""

        self.context[CONF_HOST] = self._host

        try:
            russ = Russound(self.hass.loop, self._host, self._port)
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
                CONF_HOST: self._host,
                CONF_NAME: self._name,
                CONF_PORT: self._port,
            }

            return self.async_create_entry(title=self._name, data=data)

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> ConfigFlowResult:
        """Attempt to import the existing configuration."""
        self._async_abort_entries_match({CONF_HOST: import_config[CONF_HOST]})
        self._host = import_config[CONF_HOST]
        self._name = import_config[CONF_NAME]
        self._port = import_config.get(CONF_PORT, self._port)

        return await self.async_step_pairing()
