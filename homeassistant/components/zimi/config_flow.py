"""Config flow for zcc integration."""

from __future__ import annotations

import contextlib
import logging
import socket
from typing import Any

import voluptuous as vol
from zcc import (
    ControlPoint,
    ControlPointDescription,
    ControlPointDiscoveryService,
    ControlPointError,
)

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.helpers.device_registry import format_mac

from . import async_connect_to_controller
from .const import DOMAIN, TITLE

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=""): str,
        vol.Required(CONF_PORT, default=5003): int,
        vol.Optional(CONF_MAC, default=""): str,
    }
)


def _error_tuple(base: str, error_detail: Any) -> tuple[dict[str, str], dict[str, str]]:
    """Build an error and description tuple."""
    if not error_detail:
        return ({"base": base}, {})
    return ({"base": base}, {"error_detail": str(error_detail)})


class ZimiConfigException(Exception):
    """Base class for ZimiConfig exceptions."""

    CANNOT_CONNECT = "cannot_connect"
    CONNECTION_REFUSED = "connection_refused"
    DISCOVERY_FAILURE = "discovery_failure"
    INVALID_HOST = "invalid_host"
    INVALID_MAC = "invalid_mac"
    MISMATCHED_MAC = "mismatched_mac"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"

    def __init__(self, *args, **kwargs) -> None:
        """Initialise ZimiConfigException allowing passing of error_detail."""
        super().__init__(*args)
        self.error_base = args[0]
        try:
            self.error_detail = args[1]
        except IndexError:
            self.error_detail = None


class ZimiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for zcc."""

    api: ControlPoint | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial auto-discovery step."""

        api_description: ControlPointDescription | None = None
        data: dict[str, Any] = {}
        details: dict[str, str] = {}
        errors: dict[str, str] = {}

        try:
            api_description = await ControlPointDiscoveryService().discover()
        except ControlPointError as _:
            errors["base"] = ZimiConfigException.DISCOVERY_FAILURE

        if api_description:
            data[CONF_HOST] = api_description.host
            data[CONF_PORT] = api_description.port

            with contextlib.suppress(ControlPointError):
                self.api = await async_connect_to_controller(
                    data[CONF_HOST], data[CONF_PORT], fast=True
                )

            if self.api and self.api.ready:
                data[CONF_MAC] = self.api.mac

        return self.async_show_form(
            step_id="finish",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, data
            ),
            errors=errors,
            description_placeholders=details,
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the final step."""

        data: dict[str, Any] = {}
        details: dict[str, str] = {}
        errors: dict[str, str] = {}

        if user_input is not None:
            data[CONF_HOST] = user_input[CONF_HOST]
            data[CONF_PORT] = user_input[CONF_PORT]
            data[CONF_MAC] = user_input[CONF_MAC]

            (errors, details) = await self.check_errors(
                data[CONF_HOST], data[CONF_PORT], data[CONF_MAC]
            )

            if not errors:
                if details:
                    data[CONF_MAC] = details.get("mac", None)
                await self.async_set_unique_id(data[CONF_MAC])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=TITLE, data=data)

        return self.async_show_form(
            step_id="finish",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, data
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
            return _error_tuple(ZimiConfigException.INVALID_HOST, e)
        if hostbyname:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            try:
                s.connect((host, port))
                s.close()
            except ConnectionRefusedError as e:
                return _error_tuple(ZimiConfigException.CONNECTION_REFUSED, e)
            except TimeoutError as e:
                return _error_tuple(ZimiConfigException.TIMEOUT, e)
            except socket.gaierror as e:
                return _error_tuple(ZimiConfigException.CANNOT_CONNECT, e)
        else:
            return _error_tuple(ZimiConfigException.INVALID_HOST, None)

        if mac != "" and mac is format_mac(mac):
            return _error_tuple(ZimiConfigException.INVALID_MAC, None)

        if not self.api or not self.api.ready:
            try:
                self.api = await async_connect_to_controller(host, port, fast=True)
            except ControlPointError as e:
                return _error_tuple(ZimiConfigException.CANNOT_CONNECT, e)

        if self.api:
            if mac == "":  # If no mac was given, grab mac from zcc and return
                mac = self.api.mac
                self.api.disconnect()
                return ({}, {"mac": mac})
            if format_mac(mac) != format_mac(self.api.mac):
                msg = f"{format_mac(mac)} != {format_mac(self.api.mac)}"
                _LOGGER.error("Configured mac mismatch: %s", msg)
                self.api.disconnect()
                return _error_tuple(ZimiConfigException.MISMATCHED_MAC, msg)
        else:
            return _error_tuple(ZimiConfigException.CANNOT_CONNECT, None)

        self.api.disconnect()
        return ({}, {})
