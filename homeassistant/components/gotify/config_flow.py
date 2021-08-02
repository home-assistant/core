"""Config flow for gotify integration."""
from __future__ import annotations

import logging
from typing import Any

import gotify
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import CONF_HOST, CONF_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, host: str, token: str) -> None:
    """Validate the user input allows us to connect."""
    try:
        cv.url(host)
    except vol.Invalid as error:
        raise InvalidURL from error

    gotify.config(base_url=host, app_token=token, client_token=token)

    try:
        await hass.async_add_executor_job(gotify.get_health)
    except gotify.GotifyError as exc:
        raise CannotConnect from exc

    try:
        await hass.async_add_executor_job(
            gotify.create_message, "Home Assistant has been authenticated."
        )
    except gotify.GotifyError:
        raise InvalidAuth


class GotifyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for gotify."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                await validate_input(
                    self.hass, user_input[CONF_HOST], user_input[CONF_TOKEN]
                )
            except InvalidURL:
                errors["base"] = "invalid_host"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )
        else:
            user_input = {}

        STEP_USER_DATA_SCHEMA = vol.Schema(
            {
                vol.Required(CONF_HOST, default=user_input.get(CONF_HOST)): str,
                vol.Required(CONF_TOKEN, default=user_input.get(CONF_TOKEN)): str,
            },
        )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidURL(HomeAssistantError):
    """Error to indicate there is invalid host."""
