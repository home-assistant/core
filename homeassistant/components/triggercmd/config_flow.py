"""Config flow for TRIGGERcmd integration."""

from __future__ import annotations

import logging
from typing import Any

import jwt
from triggercmd import TRIGGERcmdConnectionError, client
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({(CONF_TOKEN): str})


async def validate_input(hass: HomeAssistant, data: dict) -> str:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    if len(data[CONF_TOKEN]) < 100:
        raise InvalidToken

    token_data = jwt.decode(data[CONF_TOKEN], options={"verify_signature": False})
    if not token_data["id"]:
        raise InvalidToken

    try:
        await client.async_connection_test(data[CONF_TOKEN])
    except Exception as e:
        raise TRIGGERcmdConnectionError from e
    else:
        return token_data["id"]


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
                identifier = await validate_input(self.hass, user_input)
            except InvalidToken:
                errors[CONF_TOKEN] = "invalid_token"
            except TRIGGERcmdConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(identifier)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title="TRIGGERcmd Hub", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class InvalidToken(HomeAssistantError):
    """Invalid token."""
