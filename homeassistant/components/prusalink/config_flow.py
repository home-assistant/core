"""Config flow for PrusaLink integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import ClientError
import async_timeout
from pyprusalink import InvalidAuth, PrusaLink
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def add_protocol(value: str) -> str:
    """Validate URL has a scheme."""
    if value.startswith(("http://", "https://")):
        return value

    return f"http://{value}"


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host"): vol.All(str, add_protocol),
        vol.Required("api_key"): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, str]) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    api = PrusaLink(async_get_clientsession(hass), data["host"], data["api_key"])

    try:
        async with async_timeout.timeout(5):
            version = await api.get_version()

    except (asyncio.TimeoutError, ClientError) as err:
        _LOGGER.error("Could not connect to PrusaLink: %s", err)
        raise CannotConnect from err

    return {"title": version["hostname"]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PrusaLink."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
