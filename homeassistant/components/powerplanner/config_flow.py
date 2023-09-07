"""Config flow for powe rplanner integration."""
from __future__ import annotations

import logging
from typing import Any

from powerplanner import PowerplannerHub
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import API_KEY, DOMAIN, NAME

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(API_KEY): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user api key allows us to connect."""
    hub = PowerplannerHub(data[API_KEY])

    if not await hub.authenticate():
        raise InvalidAuth

    return {"title": NAME}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PowerPlanner."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle add the api key."""
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


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid hostname."""


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
