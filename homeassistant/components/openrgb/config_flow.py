"""Config flow for the OpenRGB integration."""

from __future__ import annotations

import logging
from typing import Any

from openrgb import OpenRGBClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import CONNECTION_ERRORS, DEFAULT_CLIENT_NAME, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


async def validate_input(hass: HomeAssistant, host: str, port: int) -> None:
    """Validate the user input allows us to connect."""

    def _try_connect(host: str, port: int) -> None:
        client = OpenRGBClient(host, port, DEFAULT_CLIENT_NAME)
        client.disconnect()

    await hass.async_add_executor_job(_try_connect, host, port)


class OpenRGBConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenRGB."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_NAME]
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            # Prevent duplicate entries
            self._async_abort_entries_match({CONF_HOST: host, CONF_PORT: port})

            try:
                await validate_input(self.hass, host, port)
            except CONNECTION_ERRORS:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception(
                    "Unknown error while connecting to OpenRGB SDK server at %s",
                    f"{host}:{port}",
                )
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_NAME: name,
                        CONF_HOST: host,
                        CONF_PORT: port,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_DATA_SCHEMA, suggested_values=user_input
            ),
            errors=errors,
        )
