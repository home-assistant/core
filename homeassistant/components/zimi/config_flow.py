"""Config flow for zcc integration."""

from __future__ import annotations

import logging
import socket
from typing import Any

import voluptuous as vol
from zcc import ControlPointDiscoveryService, ControlPointError

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN, MAC, TIMEOUT, VERBOSITY, WATCHDOG

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=5003): int,
        vol.Required(MAC): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for zcc."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        data = {}
        errors = {}

        try:
            data = await self.validate_input(user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except ConnectionRefused:
            errors["base"] = "connection_refused"
        except DiscoveryFailure:
            errors["base"] = "discovery_failure"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except InvalidHost:
            errors["base"] = "invalid_host"
        except TimeOut:
            errors["base"] = "timeout"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception during configuration steps")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(data["mac"])
            return self.async_create_entry(title=data["title"], data=data)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def validate_input(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate the user input."""

        data[TIMEOUT] = 3
        data[VERBOSITY] = 1
        data[WATCHDOG] = 1800

        unformatted_mac = data[MAC]
        data[MAC] = format_mac(data[MAC])
        assert data[MAC] is not unformatted_mac

        if data[CONF_PORT] is None:
            data[CONF_PORT] = 5003

        if data[CONF_HOST] == "":
            try:
                description = await ControlPointDiscoveryService().discover()
                data[CONF_HOST] = description.host
                data[CONF_PORT] = description.port
            except ControlPointError as e:
                raise DiscoveryFailure(e) from e
        else:
            try:
                socket.gethostbyname(data[CONF_HOST])
            except Exception as e:
                raise InvalidHost from e
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(10)
                s.connect((data[CONF_HOST], data[CONF_PORT]))
            except ConnectionRefusedError as e:
                raise ConnectionRefused from e
            except TimeoutError as e:
                raise TimeOut from e
            except Exception as e:
                raise CannotConnect from e

        # Return info that you want to store in the config entry.
        return {
            "title": "ZIMI Controller",
            "host": data[CONF_HOST],
            "port": data[CONF_PORT],
            "timeout": data[TIMEOUT],
            "verbosity": data[VERBOSITY],
            "watchdog": data[WATCHDOG],
            "mac": data[MAC],
        }


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class ConnectionRefused(HomeAssistantError):
    """Error to indicate connection was refused."""


class DiscoveryFailure(HomeAssistantError):
    """Error to indicate that Zimi UDP discovery failed."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidHost(HomeAssistantError):
    """Error to indicate that host IP address is invalid."""


class TimeOut(HomeAssistantError):
    """Error to indicate timeout when attempting to connect."""
