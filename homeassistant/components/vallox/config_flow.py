"""Config flow for the Vallox integration."""
from __future__ import annotations

from contextlib import suppress
import ipaddress
import logging
import re
from typing import Any

from vallox_websocket_api import Vallox
from vallox_websocket_api.exceptions import ValloxApiException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
    }
)


def host_valid(host: str) -> bool:
    """Return True if hostname or IP address is valid."""
    with suppress(ValueError):
        if ipaddress.ip_address(host).version in [4, 6]:
            return True

    disallowed = re.compile(r"[^a-zA-Z\d\-]")
    return all(x and not disallowed.search(x) for x in host.split("."))


async def validate_host(hass: HomeAssistant, host: str, name: str) -> dict[str, Any]:
    """Validate that the user input allows us to connect."""

    if not host_valid(host):
        raise InvalidHost(f"Invalid host: {host}")

    client = Vallox(host)

    try:
        info = await client.get_info()
    except (OSError, ValloxApiException) as err:
        raise CannotConnect("Failed to connect") from err

    return {"title": name, "model": info["model"]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Vallox integration."""

    VERSION = 1

    async def async_step_import(self, data: dict[str, Any]) -> FlowResult:
        """Handle import from YAML."""
        name = data[CONF_NAME]
        host = data[CONF_HOST]

        self._async_abort_entries_match({CONF_HOST: host})

        reason = None
        try:
            info = await validate_host(self.hass, host, name)
        except InvalidHost:
            _LOGGER.exception("An invalid host is configured for Vallox")
            reason = "invalid_host"
        except CannotConnect:
            _LOGGER.exception("Cannot connect to Vallox")
            reason = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            reason = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=data)

        return self.async_abort(reason=reason)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None or user_input[CONF_HOST] is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        name = user_input[CONF_NAME]
        host = user_input[CONF_HOST]

        self._async_abort_entries_match({CONF_HOST: host})

        try:
            info = await validate_host(self.hass, host, name)
        except InvalidHost:
            errors[CONF_HOST] = "invalid_host"
        except CannotConnect:
            errors[CONF_HOST] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors[CONF_HOST] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class InvalidHost(HomeAssistantError):
    """Error to indicate an invalid host was input."""


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
