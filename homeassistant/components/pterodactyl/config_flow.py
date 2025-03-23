"""Config flow for the Pterodactyl integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL

from .api import (
    PterodactylAPI,
    PterodactylConfigurationError,
    PterodactylConnectionError,
)
from .const import DOMAIN

DEFAULT_URL = "http://localhost:8080"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default=DEFAULT_URL): str,
        vol.Required(CONF_API_KEY): str,
    }
)


class PterodactylConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pterodactyl."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_URL]
            api_key = user_input[CONF_API_KEY]

            self._async_abort_entries_match({CONF_URL: host})
            api = PterodactylAPI(self.hass, host, api_key)

            try:
                await api.async_init()
            except (PterodactylConfigurationError, PterodactylConnectionError):
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=host, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
