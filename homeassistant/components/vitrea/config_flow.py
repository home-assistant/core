"""Vitrea config flow for UI setup."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from vitreaclient import VitreaClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class VitreaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Vitrea."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            # Validate host
            if not host or host.strip() == "":
                errors["host"] = "invalid_host"

            if not errors:
                # Always use _async_test_connection for patchable connection test
                try:
                    await self._async_test_connection(host, port)
                except ConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception:  # noqa: BLE001
                    errors["base"] = "unknown"
                else:
                    await self.async_set_unique_id(f"vitrea_{host}_{port}")
                    result = self._abort_if_unique_id_configured()
                    if result is not None:
                        return result
                    return self.async_create_entry(
                        title=f"Vitrea {host}:{port}", data=user_input
                    )

        # Always return a FlowResult, even after errors
        data_schema = self._get_schema()
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    def _get_schema(self) -> vol.Schema:
        """Get the schema for the user step."""
        return vol.Schema(
            {
                vol.Required(CONF_HOST, default="192.168.1.136"): cv.string,
                vol.Required(CONF_PORT, default=11502): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
            }
        )

    async def _async_test_connection(self, host: str, port: int) -> None:
        """Test connection to the Vitrea device using VitreaClient with a timeout."""
        client = VitreaClient(host, port)
        # Use a timeout to avoid hanging the config flow on unresponsive devices
        await asyncio.wait_for(client.connect(), timeout=5)
