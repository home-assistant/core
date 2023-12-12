"""Config flow for krisinformation integration."""
from __future__ import annotations

# Importing necessary modules and classes.
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

# Importing custom constants and exceptions from the integration.
from .const import CONF_COUNTY, COUNTY_CODES, DEFAULT_NAME, DOMAIN

# Creating a logger for the module.
_LOGGER = logging.getLogger(__name__)

# Defining the user data schema for the configuration step.
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
        vol.Required(CONF_COUNTY): SelectSelector(
            SelectSelectorConfig(
                options=sorted(COUNTY_CODES.values()),
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_COUNTY,
            )
        ),
    }
)


class PlaceholderHub:
    """Placeholder class to make tests pass."""

    def __init__(self, host: str) -> None:
        """Initialize."""
        self.host = host

    async def authenticate(self, username: str, password: str) -> bool:
        """Test if we can authenticate with the host."""
        return True


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    if not data[CONF_COUNTY]:
        raise InvalidCounty

    # Return info that you want to store in the config entry.
    return {"title": data[CONF_NAME]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for krisinformation."""

    VERSION = 1

    # Step to handle user input during configuration
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except InvalidCounty:
                errors["base"] = "invalid_county"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Custom class to handle error to indicate we cannot connect."""


class InvalidCounty(HomeAssistantError):
    """Custom class to handle error to indicate there is invalid county."""
