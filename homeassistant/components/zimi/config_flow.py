"""Config flow for zcc integration."""

from __future__ import annotations

import logging
import socket
from typing import Any

import voluptuous as vol
from zcc import ControlPointDiscoveryService, ControlPointError

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import format_mac

from . import async_connect_to_controller
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=5003): int,
        vol.Required(CONF_MAC): str,
    }
)


class ZimiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for zcc."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        if user_input is not None:
            data: dict[str, Any] = {"title": "ZIMI Controller"}

            try:
                if not user_input[CONF_HOST]:
                    try:
                        description = await ControlPointDiscoveryService().discover()
                    except ControlPointError:
                        errors["base"] = "discovery_failure"
                    data[CONF_HOST] = description.host
                    data[CONF_PORT] = description.port
                else:
                    hostbyname = None
                    data[CONF_HOST] = user_input[CONF_HOST]
                    data[CONF_PORT] = user_input[CONF_PORT]
                    try:
                        hostbyname = socket.gethostbyname(data[CONF_HOST])
                    except socket.gaierror as _:
                        errors["base"] = "invalid_host"
                    if hostbyname:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.settimeout(10)
                        try:
                            s.connect((data[CONF_HOST], data[CONF_PORT]))
                            s.close()
                        except ConnectionRefusedError:
                            errors["base"] = "connection_refused"
                        except TimeoutError:
                            errors["base"] = "timeout"
                        except socket.gaierror:
                            errors["base"] = "cannot_connect"

                data[CONF_MAC] = format_mac(user_input[CONF_MAC])
                if data[CONF_MAC] is user_input[CONF_MAC]:
                    errors["base"] = "invalid_mac"

                try:
                    api = await async_connect_to_controller(
                        data[CONF_HOST], data[CONF_PORT], fast=True
                    )

                except ConfigEntryNotReady:
                    errors["base"] = "cannot_connect"

                if api:
                    if data[CONF_MAC] != format_mac(api.mac):
                        msg = f"{data[CONF_MAC]} != {format_mac(api.mac)}"
                        _LOGGER.error("Configured mac mismatch: %s", msg)
                        errors["base"] = "mismatched_mac"
                        description_placeholders["error_detail"] = msg

                    api.disconnect()
                else:
                    errors["base"] = "cannot_connect"

            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during configuration steps")
                errors["base"] = "unknown"

            await self.async_set_unique_id(data[CONF_MAC])
            self._abort_if_unique_id_configured()

            if not errors:
                return self.async_create_entry(title=data["title"], data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders=description_placeholders,
        )
