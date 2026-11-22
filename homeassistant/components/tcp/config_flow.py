"""Config flow for the TCP integration."""

from collections.abc import Mapping
import json
import socket
import ssl
from typing import Any, override

import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PAYLOAD,
    CONF_PLATFORM,
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
    CONF_OBJECT_ID,
    CONF_TITLE,
    CONF_VALUE_ON,
    DEFAULT_BUFFER_SIZE,
    DEFAULT_SSL,
    DEFAULT_TIMEOUT,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

DATA_SCHEMA = probatio.Schema(
    {
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


def _can_connect(data: Mapping[str, Any]) -> bool:
    """Return True if the connection, including the TLS handshake, succeeds."""
    host = data[CONF_HOST]
    try:
        with socket.create_connection(
            (host, data[CONF_PORT]), data[CONF_TIMEOUT]
        ) as sock:
            if data[CONF_SSL]:
                context = ssl.create_default_context()
                if not data[CONF_VERIFY_SSL]:
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                with context.wrap_socket(sock, server_hostname=host):
                    pass
    except OSError:
        return False
    return True


PRESERVED_KEYS = (CONF_PLATFORM, CONF_OBJECT_ID)


def build_unique_id(data: Mapping[str, Any]) -> str:
    """Return the unique ID that identifies the entities of an entry."""
    return json.dumps(
        [
            data.get(key) or None
            for key in (
                CONF_HOST,
                CONF_PORT,
                CONF_PAYLOAD,
                CONF_VALUE_TEMPLATE,
                CONF_VALUE_ON,
                CONF_PLATFORM,
                CONF_OBJECT_ID,
            )
        ]
    )


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
            await self.async_set_unique_id(build_unique_id(user_input))
            self._abort_if_unique_id_configured()
            if await self.hass.async_add_executor_job(_can_connect, user_input):
                return self.async_create_entry(
                    title=f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}",
                    data=user_input,
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
            data = {
                **{key: entry.data[key] for key in PRESERVED_KEYS if key in entry.data},
                **user_input,
            }
            unique_id = build_unique_id(data)
            await self.async_set_unique_id(unique_id)
            existing = self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, unique_id
            )
            if existing and existing.entry_id != entry.entry_id:
                return self.async_abort(reason="already_configured")
            if await self.hass.async_add_executor_job(_can_connect, user_input):
                return self.async_update_reload_and_abort(
                    entry, unique_id=unique_id, data=data
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
        data = dict(import_data)
        title = data.pop(CONF_TITLE, None) or f"{data[CONF_HOST]}:{data[CONF_PORT]}"
        await self.async_set_unique_id(build_unique_id(data))
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=title, data=data)
