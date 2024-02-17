"""Config flow for FYTA integration."""
from __future__ import annotations

from collections.abc import Mapping
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

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors: dict = {}
        self._entry: config_entries.ConfigEntry | None

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""

        errors = {}
        if user_input is not None:
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

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle flow upon an API authentication error."""
        self._entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reauthorization flow."""
        errors = {}
        assert self._entry is not None

        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
                errors[CONF_USERNAME] = "auth_error"
                errors[CONF_PASSWORD] = "auth_error"
            except InvalidPassword:
                errors["base"] = "invalid_auth"
                errors[CONF_PASSWORD] = "password_error"
            else:
                self.hass.config_entries.async_update_entry(
                    self._entry,
                    data={**self._entry.data, **user_input},
                )
                await self.hass.config_entries.async_reload(self._entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        data_schema = self.add_suggested_values_to_schema(
            DATA_SCHEMA,
            {CONF_USERNAME: self._entry.data[CONF_USERNAME], **(user_input or {})},
        )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=data_schema,
            description_placeholders={"FYTA username": self._entry.data[CONF_USERNAME]},
            errors=errors,
        )
