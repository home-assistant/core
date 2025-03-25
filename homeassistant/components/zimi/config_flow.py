"""Config flow for zcc integration."""

from __future__ import annotations

import contextlib
import logging
import socket
from typing import Any

from strenum import StrEnum
import voluptuous as vol
from zcc import (
    ControlPoint,
    ControlPointDescription,
    ControlPointDiscoveryService,
    ControlPointError,
)

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from . import async_connect_to_controller
from .const import DEFAULT_PORT, DOMAIN, TITLE

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=""): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)

SELECTED_HOST_AND_PORT = "selected_host_and_port"


class ZimiConfigErrors(StrEnum):
    """ZimiConfig errors."""

    ALREADY_CONFIGURED = "already_configured"
    CANNOT_CONNECT = "cannot_connect"
    CONNECTION_REFUSED = "connection_refused"
    DISCOVERY_FAILURE = "discovery_failure"
    INVALID_HOST = "invalid_host"
    INVALID_PORT = "invalid_port"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class ZimiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for zcc."""

    api: ControlPoint = None
    api_descriptions: list[ControlPointDescription]
    data: dict[str, Any]

    def __del__(self):
        """Disconnect from ZCC."""
        if self.api:
            self.api.disconnect()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial auto-discovery step."""

        self.data = {}

        try:
            self.api_descriptions = await ControlPointDiscoveryService().discovers()
        except ControlPointError as e:
            _LOGGER.error(e)
            return await self.async_step_manual()

        if len(self.api_descriptions) == 1:
            self.data[CONF_HOST] = self.api_descriptions[0].host
            self.data[CONF_PORT] = self.api_descriptions[0].port
            return await self.create_entry()

        return await self.async_step_selection()

    async def async_step_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle selection of zcc to configure if multiple are discovered."""

        errors: dict[str, str] = {}

        if user_input is not None:
            self.data[CONF_HOST] = user_input[SELECTED_HOST_AND_PORT].split(":")[0]
            self.data[CONF_PORT] = int(user_input[SELECTED_HOST_AND_PORT].split(":")[1])
            return await self.create_entry()

        available_options = [
            SelectOptionDict(
                label=f"{description.host}:{description.port}",
                value=f"{description.host}:{description.port}",
            )
            for description in self.api_descriptions
        ]

        available_schema = vol.Schema(
            {
                vol.Required(
                    SELECTED_HOST_AND_PORT, default=available_options[0]["value"]
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=available_options,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

        return self.async_show_form(
            step_id="selection", data_schema=available_schema, errors=errors
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual configuration step if needed."""

        errors: dict[str, str] = {}

        if user_input is not None:
            self.data = {**self.data, **user_input}

            errors = await self.validate_connection(
                self.data[CONF_HOST], self.data[CONF_PORT]
            )

            if not errors:
                return await self.create_entry()

        return self.async_show_form(
            step_id="manual",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, self.data
            ),
            errors=errors,
        )

    async def create_entry(self) -> ConfigFlowResult:
        """Create entry for zcc."""

        if not self.api:
            with contextlib.suppress(ControlPointError):
                self.api = await async_connect_to_controller(
                    self.data[CONF_HOST], self.data[CONF_PORT], fast=False
                )

        if self.api and self.api.ready:
            self.data[CONF_MAC] = format_mac(self.api.mac)
            self.api.disconnect()
            await self.async_set_unique_id(self.data[CONF_MAC])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"{TITLE} ({self.data[CONF_HOST]}:{self.data[CONF_PORT]})",
                data=self.data,
            )

        return self.async_abort(reason="cannot_connect")

    async def validate_connection(self, host: str, port: int) -> dict[str, str]:
        """Check for errors with configuration.

        1. Check connectivity to configured host and port; and
        2. Connect to ZCC to get mac address and store in self.data

        Return error dictionary upon failure.
        """

        try:
            hostbyname = socket.gethostbyname(host)
        except socket.gaierror as e:
            _LOGGER.error(e)
            return {"base": ZimiConfigErrors.INVALID_HOST}
        if hostbyname:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            try:
                s.connect((host, port))
                s.close()
            except ConnectionRefusedError as e:
                _LOGGER.error(e)
                return {"base": ZimiConfigErrors.CONNECTION_REFUSED}
            except TimeoutError as e:
                _LOGGER.error(e)
                return {"base": ZimiConfigErrors.TIMEOUT}
            except socket.gaierror as e:
                _LOGGER.error(e)
                return {"base": ZimiConfigErrors.CANNOT_CONNECT}
        else:
            return {"base": ZimiConfigErrors.INVALID_HOST}

        if not self.api or not self.api.ready:
            try:
                self.api = await async_connect_to_controller(host, port, fast=True)
            except ControlPointError as e:
                _LOGGER.error(e)
                return {"base": ZimiConfigErrors.CANNOT_CONNECT}

        self.data[CONF_MAC] = format_mac(self.api.mac)
        self.api.disconnect()
        self.api = None

        return {}
