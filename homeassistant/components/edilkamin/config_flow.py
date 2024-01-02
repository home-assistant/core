"""Config flow for edilkamin integration."""
from __future__ import annotations

from typing import Any, cast

import edilkamin
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


class EdilkaminHub:
    """EdilkaminHub used for testing the authentication."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Create the Edilkamin hub using the HomeAssistant instance."""
        self.hass = hass

    async def authenticate(self, username: str, password: str) -> str:
        """Authenticate with the host and return the token or raise an exception."""
        try:
            token = await self.hass.async_add_executor_job(
                edilkamin.sign_in, username, password
            )
        except Exception as exception:
            # we can't easily catch for the NotAuthorizedException directly since it
            # was created dynamically with a factory
            if exception.__class__.__name__ == "NotAuthorizedException":
                raise InvalidAuth(exception) from exception
            raise CannotConnect(exception) from exception
        return cast(str, token)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> str:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    hub = EdilkaminHub(hass)
    username = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]
    token = await hub.authenticate(username, password)
    if not token:
        raise InvalidAuth
    return token


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for edilkamin."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
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
        else:
            data = user_input
            return self.async_create_entry(title=user_input[CONF_USERNAME], data=data)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
