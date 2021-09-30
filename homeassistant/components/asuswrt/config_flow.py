"""Config flow to configure the AsusWrt integration."""
import logging
import os
import socket

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.device_tracker.const import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_DNSMASQ,
    CONF_INTERFACE,
    CONF_REQUIRE_IP,
    CONF_SSH_KEY,
    CONF_TRACK_UNKNOWN,
    DEFAULT_DNSMASQ,
    DEFAULT_INTERFACE,
    DEFAULT_SSH_PORT,
    DEFAULT_TRACK_UNKNOWN,
    DOMAIN,
    MODE_AP,
    MODE_ROUTER,
    PROTOCOL_SSH,
    PROTOCOL_TELNET,
)
from .router import get_api

RESULT_CONN_ERROR = "cannot_connect"
RESULT_UNKNOWN = "unknown"
RESULT_SUCCESS = "success"

_LOGGER = logging.getLogger(__name__)


def _is_file(value) -> bool:
    """Validate that the value is an existing file."""
    file_in = os.path.expanduser(str(value))
    return os.path.isfile(file_in) and os.access(file_in, os.R_OK)


def _get_ip(host):
    """Get the ip address from the host name."""
    try:
        return socket.gethostbyname(host)
    except socket.gaierror:
        return None


class AsusWrtFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize AsusWrt config flow."""
        self._host = None

    @callback
    def _show_setup_form(self, user_input=None, errors=None):
        """Show the setup form to the user."""

        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
                    vol.Required(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
                    ): str,
                    vol.Optional(CONF_PASSWORD): str,
                    vol.Optional(CONF_SSH_KEY): str,
                    vol.Required(CONF_PROTOCOL, default=PROTOCOL_SSH): vol.In(
                        {PROTOCOL_SSH: "SSH", PROTOCOL_TELNET: "Telnet"}
                    ),
                    vol.Required(CONF_PORT, default=DEFAULT_SSH_PORT): cv.port,
                    vol.Required(CONF_MODE, default=MODE_ROUTER): vol.In(
                        {MODE_ROUTER: "Router", MODE_AP: "Access Point"}
                    ),
                }
            ),
            errors=errors or {},
        )

    async def _async_check_connection(self, user_input):
        """Attempt to connect the AsusWrt router."""

        api = get_api(user_input)
        try:
            await api.connection.async_connect()

        except OSError:
            _LOGGER.error("Error connecting to the AsusWrt router at %s", self._host)
            return RESULT_CONN_ERROR

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unknown error connecting with AsusWrt router at %s", self._host
            )
            return RESULT_UNKNOWN

        if not api.is_connected:
            _LOGGER.error("Error connecting to the AsusWrt router at %s", self._host)
            return RESULT_CONN_ERROR

        conf_protocol = user_input[CONF_PROTOCOL]
        if conf_protocol == PROTOCOL_TELNET:
            api.connection.disconnect()
        return RESULT_SUCCESS

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return self._show_setup_form(user_input)

        errors = {}
        self._host = user_input[CONF_HOST]
        pwd = user_input.get(CONF_PASSWORD)
        ssh = user_input.get(CONF_SSH_KEY)

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
            ip_address = await self.hass.async_add_executor_job(_get_ip, self._host)
            if not ip_address:
                errors["base"] = "invalid_host"

        if not errors:
            result = await self._async_check_connection(user_input)
            if result != RESULT_SUCCESS:
                errors["base"] = result

        if errors:
            return self._show_setup_form(user_input, errors)

        return self.async_create_entry(
            title=self._host,
            data=user_input,
        )

    async def async_step_import(self, user_input=None):
        """Import a config entry."""
        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for AsusWrt."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_CONSIDER_HOME,
                    default=self.config_entry.options.get(
                        CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME.total_seconds()
                    ),
                ): vol.All(vol.Coerce(int), vol.Clamp(min=0, max=900)),
                vol.Optional(
                    CONF_TRACK_UNKNOWN,
                    default=self.config_entry.options.get(
                        CONF_TRACK_UNKNOWN, DEFAULT_TRACK_UNKNOWN
                    ),
                ): bool,
                vol.Required(
                    CONF_INTERFACE,
                    default=self.config_entry.options.get(
                        CONF_INTERFACE, DEFAULT_INTERFACE
                    ),
                ): str,
                vol.Required(
                    CONF_DNSMASQ,
                    default=self.config_entry.options.get(
                        CONF_DNSMASQ, DEFAULT_DNSMASQ
                    ),
                ): str,
            }
        )

        conf_mode = self.config_entry.data[CONF_MODE]
        if conf_mode == MODE_AP:
            data_schema = data_schema.extend(
                {
                    vol.Optional(
                        CONF_REQUIRE_IP,
                        default=self.config_entry.options.get(CONF_REQUIRE_IP, True),
                    ): bool,
                }
            )

        return self.async_show_form(step_id="init", data_schema=data_schema)
