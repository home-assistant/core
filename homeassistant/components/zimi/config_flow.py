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

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.helpers.device_registry import format_mac

from . import async_connect_to_controller
from .const import DEFAULT_PORT, DOMAIN, TITLE

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=""): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


def _error_tuple(base: str, error_detail: Any) -> tuple[dict[str, str], dict[str, str]]:
    """Build an error and description tuple."""
    if not error_detail:
        return ({"base": base}, {})
    return ({"base": base}, {"error_detail": str(error_detail)})


class ZimiConfigErrors(StrEnum):
    """ZimiConfig errors."""

    ALREADY_CONFIGURED = "already_configured"
    CANNOT_CONNECT = "cannot_connect"
    CONNECTION_REFUSED = "connection_refused"
    DISCOVERY_FAILURE = "discovery_failure"
    INVALID_HOST = "invalid_host"
    INVALID_MAC = "invalid_mac"
    INVALID_PORT = "invalid_port"
    MISMATCHED_MAC = "mismatched_mac"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class ZimiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for zcc."""

    api: ControlPoint = None
    data: dict[str, Any]

    def __del__(self):
        """Disconnect from ZCC."""
        if self.api:
            self.api.disconnect()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial auto-discovery step."""

        api_description: ControlPointDescription | None = None

        self.data = {}
        self.data[CONF_HOST] = ""
        self.data[CONF_PORT] = DEFAULT_PORT
        self.data[CONF_MAC] = ""

        try:
            api_description = await ControlPointDiscoveryService().discover()
        except ControlPointError as _:
            _LOGGER.error("ZCC Discovery failed - falling back to manual configuration")
            return await self.async_step_finish()

        if api_description:
            self.data[CONF_HOST] = api_description.host
            self.data[CONF_PORT] = api_description.port

            with contextlib.suppress(ControlPointError):
                self.api = await async_connect_to_controller(
                    self.data[CONF_HOST], self.data[CONF_PORT], fast=True
                )

            if self.api and self.api.ready:
                self.data[CONF_MAC] = format_mac(self.api.mac)

        return await self.async_step_finish()

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the final step."""

        errors: dict[str, str] = {}
        details: dict[str, str] = {}

        if user_input is not None:
            self.data[CONF_HOST] = user_input[CONF_HOST]
            self.data[CONF_PORT] = user_input[CONF_PORT]

            (errors, details) = await self.check_errors(
                self.data[CONF_HOST], self.data[CONF_PORT], self.data[CONF_MAC]
            )

            if details:
                self.data[CONF_MAC] = details.get("mac", None)

        if self.api and not errors:
            self.api.disconnect()
            self.api = None

            await self.async_set_unique_id(self.data[CONF_MAC])

            # Check if we have (re)discovered a ZCC that is already configured
            # in the ZCC discovery step which will need manual configuration.
            if (
                self.unique_id
                and self.hass.config_entries.async_entry_for_domain_unique_id(
                    self.handler, self.unique_id
                )
            ):
                (errors, details) = _error_tuple(
                    ZimiConfigErrors.ALREADY_CONFIGURED, self.data[CONF_MAC]
                )
            else:
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{TITLE} ({self.data[CONF_HOST]}:{self.data[CONF_PORT]})",
                    data=self.data,
                )

        return self.async_show_form(
            step_id="finish",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, self.data
            ),
            errors=errors,
            description_placeholders=details,
        )

    async def check_errors(
        self, host: str, port: int, mac: str
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Check for errors with configuration.

        1. Check connectivity to configured host and port; and
        2. Check mac address is valid for configured host, port and mac.

        Return error and description dictionaries upon failure.
        """

        try:
            hostbyname = socket.gethostbyname(host)
        except socket.gaierror as e:
            return _error_tuple(ZimiConfigErrors.INVALID_HOST, e)
        if hostbyname:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            try:
                s.connect((host, port))
                s.close()
            except ConnectionRefusedError as e:
                return _error_tuple(ZimiConfigErrors.CONNECTION_REFUSED, e)
            except TimeoutError as e:
                return _error_tuple(ZimiConfigErrors.TIMEOUT, e)
            except socket.gaierror as e:
                return _error_tuple(ZimiConfigErrors.CANNOT_CONNECT, e)
        else:
            return _error_tuple(ZimiConfigErrors.INVALID_HOST, None)

        if mac != "" and mac is format_mac(mac):
            return _error_tuple(ZimiConfigErrors.INVALID_MAC, None)

        if not self.api or not self.api.ready:
            try:
                self.api = await async_connect_to_controller(host, port, fast=True)
            except ControlPointError as e:
                return _error_tuple(ZimiConfigErrors.CANNOT_CONNECT, e)

        if self.api:
            if mac == "":  # If no mac was given, grab mac from zcc and return
                mac = format_mac(self.api.mac)
                return ({}, {"mac": mac})
            if format_mac(mac) != format_mac(self.api.mac):
                msg = f"{format_mac(mac)} != {format_mac(self.api.mac)}"
                _LOGGER.error("Configured mac mismatch: %s", msg)
                return _error_tuple(ZimiConfigErrors.MISMATCHED_MAC, msg)
        else:
            return _error_tuple(ZimiConfigErrors.CANNOT_CONNECT, None)

        return ({}, {})
