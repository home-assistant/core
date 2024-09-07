"""Config flow for TRIGGERcmd integration."""

from __future__ import annotations

import logging
from typing import Any

import jwt
from triggercmd import TRIGGERcmdConnectionError, client, ha
import voluptuous as vol

from homeassistant import exceptions
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant

from .const import CONF_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({(CONF_TOKEN): str})


async def test_token(token: str) -> int:
    """Test the auth token."""
    r = await client.async_list(token)
    return r.status_code


async def validate_input(hass: HomeAssistant, data: dict) -> str:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    if len(data[CONF_TOKEN]) < 100:
        raise InvalidToken

    token_data = jwt.decode(data[CONF_TOKEN], options={"verify_signature": False})
    if not token_data["id"]:
        raise InvalidToken

    status_code = await test_token(data[CONF_TOKEN])
    if not status_code == 200:
        raise InvalidToken

    return token_data["id"]


async def test_connection(errors: dict[str, Any], token: str) -> dict[str, Any]:
    """Test the connection."""
    try:
        hub = ha.Hub(token)
        await hub.connection_test()
    except TRIGGERcmdConnectionError:
        errors["connection"] = "connection_error"
    return errors


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
                title = await validate_input(self.hass, user_input)
            except InvalidToken:
                errors[CONF_TOKEN] = "invalid_token"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                errors = await test_connection(
                    errors=errors, token=user_input[CONF_TOKEN]
                )
                if errors.get("connection") != "connection_error":
                    await self.async_set_unique_id(title)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class InvalidToken(exceptions.HomeAssistantError):
    """Invalid token."""
