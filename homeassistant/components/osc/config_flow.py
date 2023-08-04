"""Config flow for OSC (Open Sound Control) integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("device"): str,
        vol.Required("host"): str,
        vol.Required("port"): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
        vol.Required("osc_address"): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OSC (Open Sound Control)."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title=user_input["device"], data=user_input)

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)
