"""Config flow for TRIGGERcmd integration."""

from __future__ import annotations

import logging
from typing import Any

import jwt
from triggercmd import client
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant

from .const import DOMAIN, TOKEN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({(TOKEN): str})


async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    if len(data[TOKEN]) < 100:
        raise InvalidToken

    tokenData = jwt.decode(data[TOKEN], options={"verify_signature": False})
    if not tokenData["id"]:
        raise InvalidToken

    r = client.list(data[TOKEN])
    if not r.status_code == 200:
        raise InvalidToken

    return {"title": tokenData["id"]}


class TriggerCMDConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except InvalidToken:
                errors[TOKEN] = "invalid_token"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["title"])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class InvalidToken(exceptions.HomeAssistantError):
    """Invalid token."""
