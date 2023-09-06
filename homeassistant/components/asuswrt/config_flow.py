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
    CONF_HOST,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
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
    PROTOCOL_SSH,
    PROTOCOL_TELNET,
)

LABEL_MAC = "LABEL_MAC"

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
        vol.Required(CONF_INTERFACE, default=DEFAULT_INTERFACE): str,
        vol.Required(CONF_DNSMASQ, default=DEFAULT_DNSMASQ): str,
    }
)


async def get_options_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Get options schema."""
    options_flow: SchemaOptionsFlowHandler
    options_flow = cast(SchemaOptionsFlowHandler, handler.parent_handler)
    if options_flow.config_entry.data[CONF_MODE] == MODE_AP:
        return OPTIONS_SCHEMA.extend(
            {
                vol.Optional(CONF_REQUIRE_IP, default=True): bool,
            }
        )
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

    @callback
    def _show_setup_form(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> FlowResult:
        """Show the setup form to the user."""

        if user_input is None:
            user_input = {}

        adv_schema = {}
        conf_password = vol.Required(CONF_PASSWORD)
        if self.show_advanced_options:
            conf_password = vol.Optional(CONF_PASSWORD)
            adv_schema[vol.Optional(CONF_PORT)] = cv.port
            adv_schema[vol.Optional(CONF_SSH_KEY)] = str

        schema = {
            vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
            vol.Required(CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")): str,
            conf_password: str,
            vol.Required(CONF_PROTOCOL, default=PROTOCOL_SSH): vol.In(
                {PROTOCOL_SSH: "SSH", PROTOCOL_TELNET: "Telnet"}
            ),
            **adv_schema,
            vol.Required(CONF_MODE, default=MODE_ROUTER): vol.In(
                {MODE_ROUTER: "Router", MODE_AP: "Access Point"}
            ),
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(schema),
            errors=errors or {},
        )

    async def _async_check_connection(
        self, user_input: dict[str, Any]
    ) -> tuple[str, str | None]:
        """Attempt to connect the AsusWrt router."""

        host: str = user_input[CONF_HOST]
        api = AsusWrtBridge.get_bridge(self.hass, user_input)
        try:
            await api.async_connect()

        except OSError:
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
            return self._show_setup_form(user_input)

        errors: dict[str, str] = {}
        host: str = user_input[CONF_HOST]

        pwd: str | None = user_input.get(CONF_PASSWORD)
        ssh: str | None = user_input.get(CONF_SSH_KEY)

        if not (pwd or ssh):
            errors["base"] = "pwd_or_ssh"
        elif ssh:
            if pwd:
                errors["base"] = "pwd_and_ssh"
            else:
                isfile = await self.hass.async_add_executor_job(_is_file, ssh)
                if not isfile:
                    errors["base"] = "ssh_not_file"

        if not errors:
            ip_address = await self.hass.async_add_executor_job(_get_ip, host)
            if not ip_address:
                errors["base"] = "invalid_host"

        if not errors:
            result, unique_id = await self._async_check_connection(user_input)
            if result == RESULT_SUCCESS:
                if unique_id:
                    await self.async_set_unique_id(unique_id)
                # we allow configure a single instance without unique id
                elif self._async_current_entries():
                    return self.async_abort(reason="invalid_unique_id")
                else:
                    _LOGGER.warning(
                        "This device does not provide a valid Unique ID."
                        " Configuration of multiple instance will not be possible"
                    )

                return self.async_create_entry(
                    title=host,
                    data=user_input,
                )

            errors["base"] = result

        return self._show_setup_form(user_input, errors)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SchemaOptionsFlowHandler:
        """Get options flow for this handler."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)
