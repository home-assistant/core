"""Config flow for the Pterodactyl integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL

from .api import (
    PterodactylAPI,
    PterodactylConfigurationError,
    PterodactylConnectionError,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

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
            url = URL(user_input[CONF_URL]).human_repr()
            api_key = user_input[CONF_API_KEY]

            self._async_abort_entries_match({CONF_URL: url})
            api = PterodactylAPI(self.hass, url, api_key)

            try:
                await api.async_init()
            except (PterodactylConfigurationError, PterodactylConnectionError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception occurred during config flow")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=url, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
