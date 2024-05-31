"""Config flow for LedSC integration."""

from __future__ import annotations

import logging
from typing import Any
import voluptuous as vol
from websc_client import WebSClientAsync as WebSClient
from websc_client.exceptions import WebSClientError

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .consts import DEFAULT_HOST, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    host = data[CONF_HOST]
    port = data[CONF_PORT]

    client = WebSClient(host, port)
    await client.connect()
    await client.disconnect()

    return {"title": f"LedSC server {host}:{port}"}


class LedSCConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LedSC."""

    VERSION = 1

    async def async_step_user(
            self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input:
            self._async_abort_entries_match(user_input)
            try:
                info = await validate_input(self.hass, user_input)
            except WebSClientError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
