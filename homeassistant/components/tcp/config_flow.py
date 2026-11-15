"""Config flow for the TCP integration."""

import socket
from typing import Any, override

import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PAYLOAD,
    CONF_PORT,
    CONF_SSL,
    CONF_TIMEOUT,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers.selector import TemplateSelector

from .const import (
    CONF_BUFFER_SIZE,
    CONF_TITLE,
    CONF_VALUE_ON,
    DEFAULT_BUFFER_SIZE,
    DEFAULT_NAME,
    DEFAULT_SSL,
    DEFAULT_TIMEOUT,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_TITLE, default=DEFAULT_NAME): str,
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_PORT): probatio.All(
            int, probatio.Range(min=1, max=65535)
        ),
        probatio.Required(CONF_PAYLOAD): str,
        probatio.Required(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): probatio.All(
            int, probatio.Range(min=1)
        ),
        probatio.Required(CONF_BUFFER_SIZE, default=DEFAULT_BUFFER_SIZE): probatio.All(
            int, probatio.Range(min=1)
        ),
        probatio.Optional(CONF_UNIT_OF_MEASUREMENT): str,
        probatio.Optional(CONF_VALUE_TEMPLATE): TemplateSelector(),
        probatio.Optional(CONF_VALUE_ON): str,
        probatio.Required(CONF_SSL, default=DEFAULT_SSL): bool,
        probatio.Required(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
    }
)


def _can_connect(data: dict[str, Any]) -> bool:
    """Return True if a TCP connection can be opened."""
    try:
        with socket.create_connection(
            (data[CONF_HOST], data[CONF_PORT]), data[CONF_TIMEOUT]
        ):
            return True
    except OSError:
        return False


def _match_keys(data: dict[str, Any]) -> dict[str, Any]:
    """Return the keys that identify a duplicate entry."""
    return {
        CONF_HOST: data[CONF_HOST],
        CONF_PORT: data[CONF_PORT],
        CONF_PAYLOAD: data[CONF_PAYLOAD],
    }


class TcpConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TCP."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(_match_keys(user_input))
            if await self.hass.async_add_executor_job(_can_connect, user_input):
                return self.async_create_entry(
                    title=user_input[CONF_TITLE], data=user_input
                )
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(DATA_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reconfigure step."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            if await self.hass.async_add_executor_job(_can_connect, user_input):
                return self.async_update_reload_and_abort(
                    entry, title=user_input[CONF_TITLE], data=user_input
                )
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                DATA_SCHEMA, user_input or entry.data
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a config from YAML."""
        self._async_abort_entries_match(_match_keys(import_data))
        if not await self.hass.async_add_executor_job(_can_connect, import_data):
            return self.async_abort(reason="cannot_connect")
        return self.async_create_entry(title=import_data[CONF_TITLE], data=import_data)
