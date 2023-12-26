"""Config flow for E3DC Hauskraftwerk integration."""
from __future__ import annotations

import ipaddress
import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_MODBUS_ADDRESS,
    DEFAULT_MODBUS_ADDRESS,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# TO_DO adjust the data schema to the data that you need

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_MODBUS_ADDRESS, default=DEFAULT_MODBUS_ADDRESS): int,
        vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
    }
)


def host_valid(host: str) -> bool:
    """Return True if hostname or IP address is valid."""
    try:
        # Check if the host is a valid IP address
        return ipaddress.ip_address(host).version in [4, 6]
    except ValueError:
        # Check if the host is a valid hostname
        disallowed = re.compile(r"[^a-zA-Z\d\-]")
        return all(part and not disallowed.search(part) for part in host.split("."))


@callback
def e3dc_modbus_entries(hass: HomeAssistant) -> set[str]:
    """Return the hosts already configured."""
    return {
        entry.data[CONF_HOST] for entry in hass.config_entries.async_entries(DOMAIN)
    }


class PlaceholderHub:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    def __init__(self, host: str) -> None:
        """Initialize."""
        self.host = host

    async def authenticate(self, username: str, password: str) -> bool:
        """Test if we can authenticate with the host."""
        return True


# async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
#    """Validate the user input allows us to connect.

#    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
#    """
# TO_DO validate the data can be used to set up a connection.

# If your PyPI package is not built with async, pass your methods
# to the executor:
# await hass.async_add_executor_job(
#     your_validate_func, data["username"], data["password"]
# )

# hub = PlaceholderHub(data["host"])

# if not await hub.authenticate(data["username"], data["password"]):
#    raise InvalidAuth

# If you cannot connect:
# throw CannotConnect
# If the authentication is wrong:
# InvalidAuth

# Return info that you want to store in the config entry.
# return {"title": "Name of the device"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for E3DC Hauskraftwerk modbus."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialisierung."""
        self.host = None

    def _host_in_configuration_exists(self, host) -> bool:
        """Return True if host exists in configuration."""
        return host in e3dc_modbus_entries(self.hass)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await self.validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except InvalidHost:
                errors["base"] = "invalid_host"
            except InvalidPort:
                errors["base"] = "invalid_port"
            except HostAlreadyConfigured:
                errors["base"] = "host_already_configured"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self.host = user_input[CONF_HOST]

                # Extract the name from the user input here or use the default value
                # self.name = user_input.get(CONF_NAME, DEFAULT_NAME)

                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def validate_input(
        self, hass: HomeAssistant, user_input: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate the user input."""

        # Extract host and port from user input
        host = user_input[CONF_HOST]
        port = user_input[CONF_PORT]

        if not host_valid(host):
            raise InvalidHost("The provided host is invalid.")

        # Check the port for validity
        try:
            # Try to convert the port to an integer
            int_port = int(port)
            if int_port < 0 or int_port > 65535:
                raise ValueError()
        except ValueError as e:
            raise InvalidPort("The provided port is invalid or out of range.") from e

        # Check if the host is already configured
        if self._host_in_configuration_exists(host):
            raise HostAlreadyConfigured("The provided host is already configured.")

        # Here you can establish a connection to your device or
        # perform further tests to ensure that the host is valid.

        # Example: Testing the connection with a hypothetical "connect_to_device" function
        # if not await connect_to_device(host):
        #    raise CannotConnect("Unable to connect to the device.")

        # For this case, we assume that the validation includes only the host.
        # In case you need to validate other information such as username, password, etc,
        # you can also add them here.

        return {"title": CONF_NAME, "host": host}


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidHost(Exception):
    """Exception for invalid host."""


class InvalidPort(Exception):
    """Exception for invalid port."""


class HostAlreadyConfigured(Exception):
    """Exception for an already configured host."""
