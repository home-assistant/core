"""Config flow for SEMS Portal integration."""
from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientSession
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_EMAIL, CONF_PASSWORD, CONF_POWERSTATIONID, CONF_TOKEN, DOMAIN
from .sems_login import login_to_sems

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_POWERSTATIONID): str,
    }
)


async def validate_input(
    session: ClientSession, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate the incoming inputs."""
    email = data[CONF_EMAIL]
    password = data[CONF_PASSWORD]

    return await login_to_sems(session, email, password)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SEMS Portal."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        websession = async_get_clientsession(self.hass)

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                token = await validate_input(websession, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_POWERSTATIONID],
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_POWERSTATIONID: user_input[CONF_POWERSTATIONID],
                        CONF_TOKEN: str(token),
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
