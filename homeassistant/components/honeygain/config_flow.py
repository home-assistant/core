"""Config flow for Honeygain integration."""
from __future__ import annotations

from json import JSONDecodeError
from typing import Any

from pyHoneygain import HoneyGain
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
)


class HoneygainHub:
    """Initialise and authenticate credentials."""

    honeygain: HoneyGain

    def __init__(self) -> None:
        """Initialize."""
        self.honeygain = HoneyGain()

    def authenticate(self, username: str, password: str) -> bool:
        """Test if we can authenticate with the API."""
        try:
            return self.honeygain.login(username, password)
        except JSONDecodeError as exc:
            LOGGER.error("Failed to connect to Honeygain for authentication")
            raise CannotConnect from exc
        except KeyError as exc:
            LOGGER.error("Failed to validate the credentials")
            raise InvalidAuth from exc


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    hub = HoneygainHub()

    if not await hass.async_add_executor_job(
        hub.authenticate, data[CONF_EMAIL], data[CONF_PASSWORD]
    ):
        raise InvalidAuth

    # Return info that you want to store in the config entry.
    return {"title": data[CONF_EMAIL]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Honeygain."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
