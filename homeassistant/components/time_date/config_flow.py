"""Adds config flow for Time & Date integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_DISPLAY_OPTIONS, DOMAIN

_LOGGER = logging.getLogger(__name__)


class TimeDateConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Time & Date integration."""

    VERSION = 1

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Import a configuration from config.yaml."""
        display_options = {
            CONF_DISPLAY_OPTIONS: config[CONF_DISPLAY_OPTIONS],
        }
        return await self.async_step_user(user_input=display_options)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user initial step."""
        errors: dict[str, str] = {}

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if self.hass.config.time_zone is None:
            errors["timezone_not_exist"] = "timezone_not_exist"
        else:
            return self.async_create_entry(title="", data=user_input or {})
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({}), errors=errors
        )
