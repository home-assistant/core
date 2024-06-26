"""Config flow for Bryant Evolution integration."""

from __future__ import annotations

import logging
from typing import Any

from evolutionhttp import BryantEvolutionLocalClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_FILENAME

from .const import CONF_SYSTEM_ID, CONF_ZONE_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_FILENAME, default="/dev/ttyUSB0"): str,
        vol.Required(CONF_SYSTEM_ID, default=1): vol.All(int, vol.Range(min=1)),
        vol.Required(CONF_ZONE_ID, default=1): vol.All(int, vol.Range(min=1)),
    }
)


async def _can_reach_device(filename: str) -> bool:
    """Return whether we can reach the device at the given filename."""
    # Verify that we can read S1Z1 to check that the device is valid.
    try:
        client = await BryantEvolutionLocalClient.get_client(1, 1, filename)
        return await client.read_hvac_mode() is not None
    except FileNotFoundError:
        _LOGGER.error("Could not open %s: not found", filename)
        return False


class BryantConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bryant Evolution."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if await _can_reach_device(user_input[CONF_FILENAME]):
                return self.async_create_entry(
                    title=f"System {user_input[CONF_SYSTEM_ID]} Zone {user_input[CONF_ZONE_ID]}",
                    data=user_input,
                )
            errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
