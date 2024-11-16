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

from .const import DOMAIN
from .coordinator import async_connect_to_coordinator

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST, default=""): str,
        vol.Optional(CONF_PORT, default=5003): int,
        vol.Required(CONF_MAC): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for zcc."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""

        if user_input is not None:
            data: dict[str, Any] = {"title": "ZIMI Controller"}
            errors: dict[str, str] = {}
            description_placeholders: dict[str, str] = {}

            try:
                if user_input[CONF_HOST] == "":
                    try:
                        description = await ControlPointDiscoveryService().discover()
                        data[CONF_HOST] = description.host
                        data[CONF_PORT] = description.port
                    except ControlPointError as _:
                        errors["base"] = "discovery_failure"
                else:
                    data[CONF_HOST] = user_input[CONF_HOST]
                    data[CONF_PORT] = user_input[CONF_PORT]
                    try:
                        hostbyname = None
                        hostbyname = socket.gethostbyname(data[CONF_HOST])
                    except socket.gaierror as _:
                        errors["base"] = "invalid_host"
                    if hostbyname:
                        try:
                            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            s.settimeout(10)
                            s.connect((data[CONF_HOST], data[CONF_PORT]))
                            s.close()
                        except ConnectionRefusedError as _:
                            errors["base"] = "connection_refused"
                        except TimeoutError as _:
                            errors["base"] = "timeout"
                        except socket.gaierror as _:
                            errors["base"] = "cannot_connect"

                data[CONF_MAC] = format_mac(user_input[CONF_MAC])
                if data[CONF_MAC] is user_input[CONF_MAC]:
                    errors["base"] = "invalid_mac"

                try:
                    api = await async_connect_to_coordinator(
                        data[CONF_HOST], data[CONF_PORT], fast=True
                    )

                    if api:
                        if data[CONF_MAC] != format_mac(api.mac):
                            msg = f"{data[CONF_MAC]} != {format_mac(api.mac)}"
                            _LOGGER.error("Configured mac mismatch: %s", msg)
                            errors["base"] = "mismatched_mac"
                            description_placeholders["error_detail"] = msg

                        api.disconnect()
                    else:
                        errors["base"] = "cannot_connect"

                except ConfigEntryNotReady:
                    errors["base"] = "cannot_connect"

            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during configuration steps")
                errors["base"] = "unknown"

            if errors:
                return self.async_show_form(
                    step_id="user",
                    data_schema=STEP_USER_DATA_SCHEMA,
                    errors=errors,
                    description_placeholders=description_placeholders,
                )

            await self.async_set_unique_id(data["mac"])
            return self.async_create_entry(title=data["title"], data=data)

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)
