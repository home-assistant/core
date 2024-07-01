"""Config flow for Bryant Evolution integration."""

from __future__ import annotations

import logging
from typing import Any

from evolutionhttp import BryantEvolutionLocalClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_FILENAME

from . import _can_reach_device
from .const import CONF_SYSTEM_ID, CONF_ZONE_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_FILENAME, default="/dev/ttyUSB0"): str,
        vol.Required(CONF_SYSTEM_ID, default=1): vol.All(int, vol.Range(min=1)),
        vol.Required(CONF_ZONE_ID, default=1): vol.All(int, vol.Range(min=1)),
    }
)


class BryantConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bryant Evolution."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                client = await BryantEvolutionLocalClient.get_client(
                    user_input[CONF_SYSTEM_ID],
                    user_input[CONF_ZONE_ID],
                    user_input[CONF_FILENAME],
                )
                if await _can_reach_device(client):
                    return self.async_create_entry(
                        title=f"System {user_input[CONF_SYSTEM_ID]} Zone {user_input[CONF_ZONE_ID]}",
                        data=user_input,
                    )
                errors["base"] = "cannot_connect"
            except FileNotFoundError:
                _LOGGER.error("Could not open %s: not found", user_input[CONF_FILENAME])
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
