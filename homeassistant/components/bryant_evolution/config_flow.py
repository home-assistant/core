"""Config flow for Bryant Evolution integration."""

from __future__ import annotations

import logging
from typing import Any

from evolutionhttp import BryantEvolutionLocalClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_FILENAME

from .const import CONF_SYSTEM_ZONE, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_FILENAME, default="/dev/ttyUSB0"): str,
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
                system_zone = [
                    (1, x)
                    for x in await BryantEvolutionLocalClient.enumerate_zones(
                        1, user_input[CONF_FILENAME]
                    )
                ] + [
                    (2, x)
                    for x in await BryantEvolutionLocalClient.enumerate_zones(
                        2, user_input[CONF_FILENAME]
                    )
                ]
                if len(system_zone) != 0:
                    return self.async_create_entry(
                        title=f"SAM at {user_input[CONF_FILENAME]}",
                        data={
                            CONF_FILENAME: user_input[CONF_FILENAME],
                            CONF_SYSTEM_ZONE: system_zone,
                        },
                    )
                errors["base"] = "cannot_connect"
            except FileNotFoundError:
                _LOGGER.error("Could not open %s: not found", user_input[CONF_FILENAME])
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
