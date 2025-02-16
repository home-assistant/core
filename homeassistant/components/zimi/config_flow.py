"""Config flow for zcc integration."""

from __future__ import annotations

import contextlib
import logging
import socket
from typing import Any

import voluptuous as vol
from zcc import ControlPoint, ControlPointDiscoveryService, ControlPointError

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import format_mac

from . import async_connect_to_controller
from .const import DOMAIN, TITLE

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=""): str,
        vol.Required(CONF_PORT, default=5003): int,
        vol.Required(CONF_MAC, default=""): str,
    }
)


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

        data: dict[str, Any] = {}
        errors: dict[str, str] = {}
        description = None
        description_placeholders: dict[str, str] = {}

        try:
            description = await ControlPointDiscoveryService().discover()
        except ControlPointError as _:
            errors["base"] = ZimiConfigException.DISCOVERY_FAILURE

        if description:
            data[CONF_HOST] = description.host
            data[CONF_PORT] = description.port

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
            description_placeholders=description_placeholders,
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the final step."""

        data: dict[str, Any] = {}
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        if user_input is not None:
            data[CONF_HOST] = user_input[CONF_HOST]
            data[CONF_PORT] = user_input[CONF_PORT]
            data[CONF_MAC] = user_input[CONF_MAC]

            try:
                self.check_host_and_port(data[CONF_HOST], data[CONF_PORT])
                await self.check_mac(data[CONF_HOST], data[CONF_PORT], data[CONF_MAC])
            except ZimiConfigException as e:
                _LOGGER.error(e)
                errors["base"] = e.error_base
                if e.error_detail:
                    _LOGGER.error(e.error_detail)
                    description_placeholders["error_detail"] = e.error_detail
            except ConfigEntryNotReady as _:
                raise

            if self.api:
                self.api.disconnect()

            if not errors:
                await self.async_set_unique_id(data[CONF_MAC])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=TITLE, data=data)

        return self.async_show_form(
            step_id="finish",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, data
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    def check_host_and_port(self, host: str, port: int):
        """Check connectivity to configured host and port.

        Raise ZimiConfigExceptions if needed.
        """

        try:
            hostbyname = socket.gethostbyname(host)
        except socket.gaierror as e:
            raise ZimiConfigException(ZimiConfigException.INVALID_HOST) from e
        if hostbyname:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            try:
                s.connect((host, port))
                s.close()
            except ConnectionRefusedError as e:
                raise ZimiConfigException(ZimiConfigException.CONNECTION_REFUSED) from e
            except TimeoutError as e:
                raise ZimiConfigException(ZimiConfigException.TIMEOUT) from e
            except socket.gaierror as e:
                raise ZimiConfigException(ZimiConfigException.CANNOT_CONNECT) from e
        else:
            raise ZimiConfigException(ZimiConfigException.INVALID_HOST)

    async def check_mac(self, host: str, port: int, mac: str):
        """Check mac address is valid for configured host, port and mac.

        Raise ZimiConfigException if needed.
        """

        if mac is format_mac(mac):
            raise ZimiConfigException(ZimiConfigException.INVALID_MAC)

        if not self.api or not self.api.ready:
            try:
                self.api = await async_connect_to_controller(host, port, fast=True)
            except ControlPointError as e:
                raise ZimiConfigException(ZimiConfigException.CANNOT_CONNECT) from e
            except ConfigEntryNotReady as _:
                raise

        if self.api:
            if format_mac(mac) != format_mac(self.api.mac):
                msg = f"{format_mac(mac)} != {format_mac(self.api.mac)}"
                _LOGGER.error("Configured mac mismatch: %s", msg)
                raise ZimiConfigException(ZimiConfigException.MISMATCHED_MAC, msg)
        else:
            raise ZimiConfigException(ZimiConfigException.CANNOT_CONNECT)
