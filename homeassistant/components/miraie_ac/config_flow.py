"""Config flow for MirAIe AC integration."""
from __future__ import annotations

import logging
from typing import Any

from py_miraie_ac import AuthType, MirAIeAPI
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
            await api.initialize()
        except Exception as ex:
            _LOGGER.error("Error connecting to MirAIe")
            raise InvalidAuth from ex

    _LOGGER.debug("Connection successful!")
    # Return info that you want to store in the config entry.
    return {"title": "MirAIe"}


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
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
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
