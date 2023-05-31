"""Config flow for Schlage integration."""
from __future__ import annotations

from typing import Any

import pyschlage
from pyschlage.exceptions import Error as PyschlageError, NotAuthorizedError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Schlage."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            try:
                await self.hass.async_add_executor_job(
                    _authenticate, username, password
                )
            except NotAuthorizedError:
                LOGGER.exception("Authentication error")
                errors["base"] = "invalid_auth"
            except PyschlageError:
                LOGGER.exception("Unknown error")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(username.lower())
                return self.async_create_entry(title=username, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


def _authenticate(username: str, password: str) -> None:
    """Authenticate with the Schlage API."""
    auth = pyschlage.Auth(username, password)
    auth.authenticate()
