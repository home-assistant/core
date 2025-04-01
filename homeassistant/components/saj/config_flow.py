"""Config flow for SAJ."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import pysaj
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.exceptions import ConfigEntryAuthFailed, Unauthorized

from .const import CONNECTION_TYPES, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SAJConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the SAJ Solar Inverter."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def _async_validate_input(
        self, user_input: dict[str, Any]
    ) -> Mapping[str, Any]:
        """Validate the user input allows us to connect."""

        host = user_input["host"]
        connection_type = user_input["type"]
        username = user_input.get("username")
        password = user_input.get("password")
        try:
            kwargs = {}
            if connection_type == CONNECTION_TYPES[0]:  # Assuming 'ethernet'
                saj = pysaj.SAJ(host)
            else:  # Assuming 'wifi'
                if username:
                    kwargs["username"] = username
                if password:
                    kwargs["password"] = password
                saj = pysaj.SAJ(host, **kwargs)

            sensor_def = pysaj.Sensors(connection_type == CONNECTION_TYPES[1])
            await saj.read(sensor_def)

        except Exception as err:
            _LOGGER.error("Connection failed for host %s: %s", host, err)
            raise ConfigEntryAuthFailed from err

        return {
            "host": host,
            "type": connection_type,
            "username": username or "",
            "password": password or "",
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow started by the user."""
        errors = {}

        if user_input is not None:
            try:
                data = await self._async_validate_input(user_input=user_input)

                return self.async_create_entry(
                    title=user_input.get("name", "SAJ Solar Inverter"), data=data
                )
            except Unauthorized:
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=self._schema,
            errors=errors or None,
        )

    @property
    def _schema(self) -> vol.Schema:
        """Define the schema for user input."""

        return vol.Schema(
            {
                vol.Required("host"): str,
                vol.Optional("name", default="SAJ Solar Inverter"): str,
                vol.Optional("type", default="ethernet"): vol.In(CONNECTION_TYPES),
                vol.Optional("username", default=""): str,
                vol.Optional("password", default=""): str,
            }
        )
