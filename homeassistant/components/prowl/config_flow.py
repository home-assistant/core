"""The config flow for the Prowl component."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    CONN_CLASS_CLOUD_POLL,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.exceptions import HomeAssistantError

from . import ProwlNotificationService
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ProwlConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Prowl component."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_CLOUD_POLL

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.api_key = ""
        self.name = "Prowl"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user configuration."""
        errors = {}
        if user_input and user_input[CONF_API_KEY]:
            self.api_key = user_input[CONF_API_KEY]
            if user_input[CONF_NAME] and len(user_input[CONF_NAME]) > 0:
                self.name = user_input[CONF_NAME]
            await self.async_set_unique_id(self.name)
            self._abort_if_unique_id_configured()
            errors = await self._validate_api_key(self.api_key)
            if not errors:
                return self.async_create_entry(
                    title=self.name,
                    data={
                        CONF_API_KEY: self.api_key,
                        CONF_NAME: self.name,
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=self._get_schema(), errors=errors
        )

    def _get_schema(self) -> vol.Schema:
        """Return the schema for the user input."""
        return vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
                vol.Required(CONF_NAME): str,
            }
        )

    async def _validate_api_key(self, api_key: str):
        """Validate the provided API key."""
        prowl = ProwlNotificationService(self.hass, api_key)
        try:
            if not await prowl.async_verify_key():
                return {"base": "invalid_api_key"}
        except TimeoutError:
            return {"base": "api_timeout"}
        except HomeAssistantError:
            _LOGGER.exception("Unexpected error")
            return {"base": "bad_api_response"}
        return {}
