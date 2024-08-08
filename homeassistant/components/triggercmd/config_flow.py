"""Config flow for TRIGGERcmd integration."""

from __future__ import annotations

import logging
from typing import Any

import jwt
from triggercmd import client
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant

from .const import DOMAIN

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

    r = client.list(data["token"])
    if not r.status_code == 200:
        raise InvalidToken

    return {"title": tokenData["id"]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

                return self.async_create_entry(title=info["title"], data=user_input)
            except InvalidToken:
                errors["token"] = "invalid_token"
                return self.async_abort(reason="invalid_token")
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
                return self.async_abort(reason="unknown")

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class InvalidToken(exceptions.HomeAssistantError):
    """Invalid token."""
