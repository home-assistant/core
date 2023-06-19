"""Config flow for MirAIe AC integration."""
from __future__ import annotations

import logging
import re
from typing import Any

from py_miraie_ac import AuthException, AuthType, MirAIeAPI
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import CONFIG_KEY_PASSWORD, CONFIG_KEY_USER_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONFIG_KEY_USER_ID): str,
        vol.Required(CONFIG_KEY_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    login_id = data[CONFIG_KEY_USER_ID]
    password = data[CONFIG_KEY_PASSWORD]

    async with MirAIeAPI(
        auth_type=AuthType.MOBILE, login_id=login_id, password=password
    ) as api:
        try:
            _LOGGER.debug("Initializing MirAIe API")

            if not _validate_mobile_number(login_id):
                raise ValidationError()

            await api.initialize()
        except ValidationError as ex:
            _LOGGER.error("Invalid Mobile Number")
            raise ValidationError from ex
        except AuthException as ex:
            _LOGGER.error("Invalid user ID or password")
            raise InvalidAuth from ex

        _LOGGER.debug("Connection successful!")
        # Return info that you want to store in the config entry.
        return {"title": "MirAIe"}


def _validate_mobile_number(mobile_number):
    pattern = r"^\+91\d{10}$"
    match = re.match(pattern, mobile_number)
    return match is not None


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MirAIe AC."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except ValidationError:
                errors["base"] = "invalid_mobile"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
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


class ValidationError(HomeAssistantError):
    """Error to indicate that the given input is invalid."""
