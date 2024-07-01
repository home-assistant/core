"""Config flow for Hello World integration."""

from __future__ import annotations

import logging
from typing import Any

import jwt
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant

from .const import DOMAIN  # pylint:disable=unused-import
from .hub import Hub

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({("token"): str})


async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    if len(data["token"]) < 100:
        raise InvalidToken

    tokenData = jwt.decode(data["token"], options={"verify_signature": False})
    if not tokenData["id"]:
        raise InvalidToken

    hub = Hub(hass, data["token"])
    result = await hub.test_connection()
    if not result:
        raise CannotConnect

    return {"title": tokenData["id"]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidToken:
                errors["token"] = "invalid_token"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error: cannot connect."""


class InvalidToken(exceptions.HomeAssistantError):
    """Invalid token."""
