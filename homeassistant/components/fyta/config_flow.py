"""Config flow for FYTA integration."""
from __future__ import annotations

import logging
from typing import Any

from fyta_cli.fyta_connector import FytaConnector
from fyta_cli.fyta_exceptions import (
    FytaAuthentificationError,
    FytaConnectionError,
    FytaPasswordError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN
from .exception import CannotConnect, InvalidAuth, InvalidPassword

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, Any]:
    """Validate if the user input is correct."""

    access_token = data.get("access_token", "")
    expiration = data.get("expiration", None)

    fyta = FytaConnector(
        data[CONF_USERNAME], data[CONF_PASSWORD], access_token, expiration
    )

    try:
        await fyta.login()
    except FytaConnectionError as ex:
        raise CannotConnect from ex
    except FytaAuthentificationError as ex:
        raise InvalidAuth from ex
    except FytaPasswordError as ex:
        raise InvalidPassword from ex

    return {"title": data[CONF_USERNAME]}


class FytaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fyta."""

    VERSION = 1

    _entry: config_entries.ConfigEntry | None = None

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors: dict = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""

        errors = {}
        if user_input:
            try:
                info = await validate_input(self.hass, user_input)

                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
                errors[CONF_USERNAME] = "auth_error"
                errors[CONF_PASSWORD] = "auth_error"
            except InvalidPassword:
                errors["base"] = "invalid_auth"
                errors[CONF_PASSWORD] = "password_error"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"

        # If there is no user input or there were errors, show the form again, including any errors that were found with the input.
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
