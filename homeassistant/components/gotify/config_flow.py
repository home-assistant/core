"""Config flow for gotify integration."""
from __future__ import annotations

import logging
from typing import Any

import gotify
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import CONF_HOST, CONF_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _get_config_schema(input_dict: dict[str, Any] = None) -> vol.Schema:
    """
    Return schema defaults for init step based on user input/config dict.

    Retain info already provided for future form views by setting them
    as defaults in schema.
    """
    if input_dict is None:
        input_dict = {}

    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=input_dict.get(CONF_HOST)): str,
            vol.Required(CONF_TOKEN, default=input_dict.get(CONF_TOKEN, "")): str,
        },
        extra=vol.REMOVE_EXTRA,
    )


class GotifyHub:
    """Gotify Server Connection test."""

    def __init__(self, hass, host: str, token: str) -> None:
        """Initialize."""
        self.host = host
        self.token = token
        gotify.config(base_url=host, app_token=token, client_token=token)

    async def connect(self, hass: HomeAssistant) -> bool:
        """Test if we can connect with the host."""
        try:
            await hass.async_add_executor_job(gotify.get_health)
        except gotify.GotifyError:
            return False
        return True

    async def authenticate(self, hass: HomeAssistant) -> bool:
        """Test if we can authenticate with the host."""
        try:
            await hass.async_add_executor_job(
                gotify.create_message, "Home Assistant has been authenticated."
            )
        except gotify.GotifyError:
            return False
        return True


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    schema = cv.url
    try:
        schema(data[CONF_HOST])
    except vol.Invalid as error:
        raise InvalidURL from error

    hub = GotifyHub(hass, data[CONF_HOST], data[CONF_TOKEN])

    result = await hub.connect(hass)
    if not result:
        raise CannotConnect

    result = await hub.authenticate(hass)
    if not result:
        raise InvalidAuth

    # Return info that you want to store in the config entry.
    return {"title": data[CONF_HOST]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for gotify."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._user_schema = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Store current values in case setup fails and user needs to edit
            self._user_schema = _get_config_schema(user_input)
            try:
                info = await validate_input(self.hass, user_input)
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
                return self.async_create_entry(title=info["title"], data=user_input)

        schema = self._user_schema or _get_config_schema()

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidURL(HomeAssistantError):
    """Error to indicate there is invalid host."""
