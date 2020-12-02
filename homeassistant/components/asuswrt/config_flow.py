"""Config flow to configure the AsusWrt integration."""
import logging
import os
import socket

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_MODE,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)
from homeassistant.helpers import config_validation as cv

# pylint:disable=unused-import
from .const import (
    CONF_DNSMASQ,
    CONF_INTERFACE,
    CONF_REQUIRE_IP,
    CONF_SSH_KEY,
    DEFAULT_DNSMASQ,
    DEFAULT_INTERFACE,
    DEFAULT_SSH_PORT,
    DOMAIN,
)
from .router import get_api

_LOGGER = logging.getLogger(__name__)


def _is_file(value) -> bool:
    """Validate that the value is an existing file."""
    file_in = os.path.expanduser(str(value))

    if not os.path.isfile(file_in):
        return False
    if not os.access(file_in, os.R_OK):
        return False
    return True


def _get_ip(host):
    """Get the ip address from the host name."""
    if host is None:
        return None
    try:
        return socket.gethostbyname(host)
    except socket.gaierror:
        return None


class AsusWrtFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize AsusWrt config flow."""
        self._host = None
        self._name = None

    def _show_setup_form(self, user_input=None, errors=None):
        """Show the setup form to the user."""

        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
                    vol.Optional(CONF_NAME, default=user_input.get(CONF_NAME, "")): str,
                    vol.Required(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
                    ): str,
                    vol.Optional(CONF_PASSWORD): str,
                    vol.Optional(CONF_SSH_KEY): str,
                    vol.Required(CONF_PROTOCOL, default="ssh"): vol.In(
                        {"ssh": "SSH", "telnet": "Telnet"}
                    ),
                    vol.Required(CONF_PORT, default=DEFAULT_SSH_PORT): cv.port,
                    vol.Required(CONF_MODE, default="router"): vol.In(
                        {"router": "Router", "ap": "Access Point"}
                    ),
                    vol.Required(CONF_REQUIRE_IP, default=True): bool,
                    vol.Required(CONF_INTERFACE, default=DEFAULT_INTERFACE): str,
                    vol.Required(CONF_DNSMASQ, default=DEFAULT_DNSMASQ): str,
                }
            ),
            errors=errors or {},
        )

    async def _async_check_connection(self, user_input):
        """Attempt to connect the AsusWrt router."""

        errors = {}

        api = get_api(user_input)
        try:
            await api.connection.async_connect()
            if api.is_connected:
                if hasattr(api.connection, "disconnect"):
                    await api.connection.disconnect()

                return self.async_create_entry(
                    title=self._name,
                    data=user_input,
                )

            _LOGGER.error("Error connecting to the AsusWrt router at %s", self._host)
            errors["base"] = "cannot_connect"

        except OSError:
            _LOGGER.error("Error connecting to the AsusWrt router at %s", self._host)
            errors["base"] = "cannot_connect"

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unknown error connecting with AsusWrt router at %s", self._host
            )
            errors["base"] = "unknown"

        return self._show_setup_form(user_input, errors)

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}

        if user_input is None:
            return self._show_setup_form(user_input, errors)

        host = user_input[CONF_HOST]
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
            ip_address = await self.hass.async_add_executor_job(_get_ip, host)
            if not ip_address:
                errors["base"] = "invalid_host"

        if errors:
            return self._show_setup_form(user_input, errors)

        self._host = host
        self._name = user_input.get(CONF_NAME, host)

        # Check if already configured
        await self.async_set_unique_id(ip_address)
        self._abort_if_unique_id_configured()

        return await self._async_check_connection(user_input)

    async def async_step_import(self, user_input=None):
        """Import a config entry."""
        return await self.async_step_user(user_input)
