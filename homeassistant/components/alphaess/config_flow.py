"""Config flow for AlphaEss integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
from alphaess import alphaess
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    client = alphaess.alphaess()

    try:
        await client.authenticate(data["username"], data["password"])

    except aiohttp.ClientResponseError as e:
        if e.status == 401:
            raise InvalidAuth
        else:
            raise UnknownError
    except aiohttp.client_exceptions.ClientConnectorError:
        raise CannotConnect

    else:
        return {"AlphaESS": data["username"]}


class AlphaESSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Alpha ESS."""

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
            await validate_input(self.hass, user_input)

        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except UnknownError:
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(
                title=user_input["username"], data=user_input
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class CannotConnect(HomeAssistantError):
    """Error to indicate there is a problem connecting."""


class UnknownError(HomeAssistantError):
    """Error to indicate there is an unknown error."""
