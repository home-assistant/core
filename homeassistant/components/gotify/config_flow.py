"""Config flow for gotify integration."""
from __future__ import annotations

import logging
from typing import Any

import gotify
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_CLIENT_SECRET, CONF_HOST, CONF_NAME, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, user_input: dict) -> None:
    """Validate the user input allows us to connect."""
    try:
        cv.url(user_input[CONF_HOST])
    except vol.Invalid as error:
        raise InvalidURL from error

    gotify_hub = gotify.gotify(
        base_url=user_input[CONF_HOST], client_token=user_input[CONF_CLIENT_SECRET]
    )

    try:
        await hass.async_add_executor_job(gotify_hub.get_health)
    except gotify.GotifyError as exc:
        raise CannotConnect from exc

    try:
        await hass.async_add_executor_job(gotify_hub.get_applications)
    except gotify.GotifyError as error:
        raise InvalidAuth from error


def sanitise_name(hass: HomeAssistant, name: str) -> str:
    """Make sure we are not going to create and entry with a duplicate name as this would produce duplicate services."""

    raw_name = DOMAIN + "_" + name.replace(" ", "_").lower()

    if DOMAIN in hass.data:
        entry_names = []
        for entry in hass.data[DOMAIN]:
            entry_names.append(hass.data[DOMAIN][entry].data[CONF_NAME])

    name = raw_name
    i = 2
    while name in entry_names:
        name = raw_name + str(i)
    return name


async def configure_application(hass: HomeAssistant, user_input: dict):
    """Configure and existing gotify application or create a new one."""
    gotify_hub = gotify.gotify(
        base_url=user_input[CONF_HOST], client_token=user_input[CONF_CLIENT_SECRET]
    )

    return_token = ""
    return_name = ""

    try:
        current_applications = await hass.async_add_executor_job(
            gotify_hub.get_applications
        )
        if CONF_TOKEN in user_input:
            for app in current_applications:
                if user_input[CONF_TOKEN] == app.get("token"):
                    return_token = user_input[CONF_TOKEN]
                    return_name = app.get("name")
        if not (CONF_TOKEN in user_input) or not return_token:
            new_app = await hass.async_add_executor_job(
                gotify_hub.create_application, "Home Assistant"
            )
            return_token = new_app.get("token")
            return_name = new_app.get("name")
    except gotify.GotifyError as error:
        raise AppSetupError from error

    # Sanitise name returned from Gotify API
    return_name = sanitise_name(hass, return_name)
    return return_token, return_name


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
                await validate_input(self.hass, user_input)
                (
                    user_input[CONF_TOKEN],
                    user_input[CONF_NAME],
                ) = await configure_application(self.hass, user_input)
            except InvalidURL:
                errors["base"] = "invalid_host"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except AppSetupError:
                errors["base"] = "app_setup_error"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
        else:
            user_input = {}

        step_user_data_scheme = vol.Schema(
            {
                vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
                vol.Required(CONF_CLIENT_SECRET): str,
                vol.Optional(CONF_TOKEN): str,
            },
        )

        return self.async_show_form(
            step_id="user", data_schema=step_user_data_scheme, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidURL(HomeAssistantError):
    """Error to indicate there is invalid host."""


class AppSetupError(HomeAssistantError):
    """Error to indicate failure to setup Gotify application."""
