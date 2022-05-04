"""Config flow to configure the AsusWrt integration."""

from __future__ import annotations

import logging
import os
import socket
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import (
    CONF_BASE,
    CONF_HOST,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)

from .bridge import AsusWrtBridge
from .const import (
    CONF_DNSMASQ,
    CONF_INTERFACE,
    CONF_REQUIRE_IP,
    CONF_SSH_KEY,
    CONF_TRACK_UNKNOWN,
    DEFAULT_DNSMASQ,
    DEFAULT_INTERFACE,
    DEFAULT_TRACK_UNKNOWN,
    DOMAIN,
    MODE_AP,
    MODE_ROUTER,
    PROTOCOL_HTTP,
    PROTOCOL_HTTPS,
    PROTOCOL_SSH,
    PROTOCOL_TELNET,
)

ALLOWED_PROTOCOL = {
    PROTOCOL_HTTP: "HTTP",
    PROTOCOL_HTTPS: "HTTPS",
    PROTOCOL_SSH: "SSH",
    PROTOCOL_TELNET: "Telnet",
}

RESULT_CONN_ERROR = "cannot_connect"
RESULT_SUCCESS = "success"
RESULT_UNKNOWN = "unknown"

_LOGGER = logging.getLogger(__name__)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_CONSIDER_HOME, default=DEFAULT_CONSIDER_HOME.total_seconds()
        ): vol.All(vol.Coerce(int), vol.Clamp(min=0, max=900)),
        vol.Optional(CONF_TRACK_UNKNOWN, default=DEFAULT_TRACK_UNKNOWN): bool,
    }
)


async def get_options_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Get options schema."""
    options_flow: SchemaOptionsFlowHandler
    options_flow = cast(SchemaOptionsFlowHandler, handler.parent_handler)
    used_protocol = options_flow.config_entry.data[CONF_PROTOCOL]
    if used_protocol in [PROTOCOL_SSH, PROTOCOL_TELNET]:
        data_schema = OPTIONS_SCHEMA.extend(
            {
                vol.Required(CONF_INTERFACE, default=DEFAULT_INTERFACE): str,
                vol.Required(CONF_DNSMASQ, default=DEFAULT_DNSMASQ): str,
            }
        )
        if options_flow.config_entry.data[CONF_MODE] == MODE_AP:
            return data_schema.extend(
                {
                    vol.Optional(CONF_REQUIRE_IP, default=True): bool,
                }
            )
        return data_schema

    return OPTIONS_SCHEMA


OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(get_options_schema),
}


def _is_file(value: str) -> bool:
    """Validate that the value is an existing file."""
    file_in = os.path.expanduser(value)
    return os.path.isfile(file_in) and os.access(file_in, os.R_OK)


def _get_ip(host: str) -> str | None:
    """Get the ip address from the host name."""
    try:
        return socket.gethostbyname(host)
    except socket.gaierror:
        return None


class AsusWrtFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the AsusWrt config flow."""
        self._config_data: dict[str, Any] = {}
        self._error: str | None = None

    @callback
    def _show_setup_form(self, error: str | None = None) -> FlowResult:
        """Show the setup form to the user."""

        base_err = error or self._error
        self._error = None
        user_input = self._config_data

        schema = {
            vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
            vol.Required(CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")): str,
            vol.Optional(CONF_PASSWORD): str,
            vol.Required(
                CONF_PROTOCOL, default=user_input.get(CONF_PROTOCOL, PROTOCOL_HTTP)
            ): vol.In(ALLOWED_PROTOCOL),
        }
        if self.show_advanced_options:
            schema[vol.Optional(CONF_PORT)] = cv.port

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(schema),
            errors={CONF_BASE: base_err} if base_err else None,
        )

    @callback
    def _show_legacy_form(self, error: str | None = None) -> FlowResult:
        """Show the setup form to the user for legacy options."""

        ssh_schema = {}
        protocol = self._config_data[CONF_PROTOCOL]
        if protocol == PROTOCOL_SSH and CONF_PASSWORD not in self._config_data:
            ssh_schema[vol.Required(CONF_SSH_KEY)] = str

        schema = {
            **ssh_schema,
            vol.Required(CONF_MODE, default=MODE_ROUTER): vol.In(
                {MODE_ROUTER: "Router", MODE_AP: "Access Point"}
            ),
        }

        return self.async_show_form(
            step_id="legacy",
            data_schema=vol.Schema(schema),
            errors={CONF_BASE: error} if error else None,
        )

    async def _async_check_connection(
        self, user_input: dict[str, Any]
    ) -> tuple[str, str | None]:
        """Attempt to connect the AsusWrt router."""

        host: str = user_input[CONF_HOST]
        api = AsusWrtBridge.get_bridge(self.hass, user_input)
        try:
            await api.async_connect()

        except ConfigEntryNotReady:
            _LOGGER.error("Error connecting to the AsusWrt router at %s", host)
            return RESULT_CONN_ERROR, None

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unknown error connecting with AsusWrt router at %s", host
            )
            return RESULT_UNKNOWN, None

        if not api.is_connected:
            _LOGGER.error("Error connecting to the AsusWrt router at %s", host)
            return RESULT_CONN_ERROR, None

        unique_id = api.label_mac
        await api.async_disconnect()

        return RESULT_SUCCESS, unique_id

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""

        # if there's one entry without unique ID, we abort config flow
        for unique_id in self._async_current_ids():
            if unique_id is None:
                return self.async_abort(reason="no_unique_id")

        if user_input is None:
            return self._show_setup_form()

        self._config_data = user_input
        protocol: str = user_input[CONF_PROTOCOL]
        pwd: str | None = user_input.get(CONF_PASSWORD)

        if not pwd and protocol != PROTOCOL_SSH:
            return self._show_setup_form(error="pwd_required")

        host: str = user_input[CONF_HOST]
        ip_address = await self.hass.async_add_executor_job(_get_ip, host)
        if not ip_address:
            return self._show_setup_form(error="invalid_host")

        if protocol in [PROTOCOL_SSH, PROTOCOL_TELNET]:
            return await self.async_step_legacy()

        result, unique_id = await self._async_check_connection(user_input)
        if result == RESULT_SUCCESS:
            return await self._async_save_entry(unique_id)

        return self._show_setup_form(error=result)

    async def async_step_legacy(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow for legacy settings."""
        if user_input is None:
            return self._show_legacy_form()

        self._config_data.update(user_input)
        if ssh := user_input.get(CONF_SSH_KEY):
            if not await self.hass.async_add_executor_job(_is_file, ssh):
                return self._show_legacy_form(error="ssh_not_file")

        result, unique_id = await self._async_check_connection(self._config_data)
        if result == RESULT_SUCCESS:
            return await self._async_save_entry(unique_id)

        self._error = result
        return await self.async_step_user()

    async def _async_save_entry(self, unique_id: str | None) -> FlowResult:
        """Save entry data if unique id is valid."""
        if unique_id:
            await self.async_set_unique_id(unique_id)
        # we allow to configure a single instance without unique id
        elif self._async_current_entries():
            return self.async_abort(reason="invalid_unique_id")
        else:
            _LOGGER.warning(
                "This device does not provide a valid Unique ID."
                " Configuration of multiple instance will not be possible"
            )

        return self.async_create_entry(
            title=self._config_data[CONF_HOST],
            data=self._config_data,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SchemaOptionsFlowHandler:
        """Get options flow for this handler."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)
