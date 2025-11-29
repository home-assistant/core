"""Config flow for the Diyanet integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DiyanetApiClient, DiyanetAuthError, DiyanetConnectionError
from .const import CONF_LOCATION_ID, DEFAULT_LOCATION_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Raised when the integration cannot connect during config flow."""


class InvalidAuth(HomeAssistantError):
    """Raised when provided credentials are invalid during config flow."""


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_LOCATION_ID, default=DEFAULT_LOCATION_ID): int,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    session = async_get_clientsession(hass)
    client = DiyanetApiClient(session, data[CONF_EMAIL], data[CONF_PASSWORD])

    # Test authentication
    await client.authenticate()

    # Test getting prayer times
    await client.get_prayer_times(data[CONF_LOCATION_ID])

    # Return info that you want to store in the config entry
    return {"title": f"Diyanet ({data[CONF_EMAIL]})"}


class DiyanetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Diyanet."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except DiyanetConnectionError:
                errors["base"] = "cannot_connect"
            except DiyanetAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Prevent duplicate entries for the same email
                await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
