"""Config flow for Bryant Evolution integration."""

from __future__ import annotations

import logging
from typing import Any

from evolutionhttp import BryantEvolutionClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST

from .const import CONF_SYSTEM_ID, CONF_ZONE_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_SYSTEM_ID, default=1): vol.All(int, vol.Range(min=1)),
        vol.Required(CONF_ZONE_ID, default=1): vol.All(int, vol.Range(min=1)),
    }
)


async def can_reach_device(host: str) -> bool:
    """Return whether we can reach the device at the given host."""
    # Verify that we can read S1Z1 to check that the host is valid.
    client = BryantEvolutionClient(host, 1, 1)
    return await client.read_hvac_mode() is not None


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bryant Evolution."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if await can_reach_device(user_input[CONF_HOST]):
                return self.async_create_entry(
                    title=f"System {user_input[CONF_SYSTEM_ID]} Zone {user_input[CONF_ZONE_ID]}",
                    data=user_input,
                )
            errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
