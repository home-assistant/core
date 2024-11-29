"""Config flow for F5 TTS Client integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .connection import ConnectionClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT): str,
    }
)


class F5ConfigFlow(ConfigFlow, domain=DOMAIN):
    """User setup flow via UI."""

    VERSION = 1
    host: str
    port: str
    s_client: ConnectionClient

    async def validate_connection(self):
        """Validate server is up and running."""
        await self.s_client.connect()
        await self.s_client.disconnect()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            self.host = user_input[CONF_HOST]
            self.port = user_input[CONF_PORT]
            self.s_client = ConnectionClient(self.host, self.port)

            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
            )

            try:
                await self.validate_connection()
                _LOGGER.info("Successfully set up F5 TTS")
                return self.async_create_entry(title="F5 TTS Client", data=user_input)
            except ConnectionRefusedError:
                errors["base"] = "cannot_connect"
            except TimeoutError:
                errors["base"] = "timeout_connect"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
