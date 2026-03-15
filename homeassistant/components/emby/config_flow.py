"""Config flow for the Emby integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.helpers import config_validation as cv

from . import _validate_connection
from .const import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_SSL_PORT,
    DOMAIN,
    CannotConnect,
    InvalidAuth,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_API_KEY): str,
        vol.Optional(CONF_PORT): cv.port,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): bool,
    }
)


class EmbyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Emby."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a user initiated config flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            api_key = user_input[CONF_API_KEY]
            ssl = user_input.get(CONF_SSL, DEFAULT_SSL)
            port = user_input.get(CONF_PORT)
            if port is None:
                port = DEFAULT_SSL_PORT if ssl else DEFAULT_PORT

            try:
                server_id = await _validate_connection(
                    self.hass, host, port, api_key, ssl
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(server_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=host,
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_API_KEY: api_key,
                        CONF_SSL: ssl,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )
