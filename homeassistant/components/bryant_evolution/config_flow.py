"""Config flow for Bryant Evolution integration."""

from __future__ import annotations

import logging
from typing import Any

from evolutionhttp import BryantEvolutionLocalClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_FILENAME
from homeassistant.helpers.typing import UNDEFINED

from .const import CONF_SYSTEM_ZONE, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_FILENAME, default="/dev/ttyUSB0"): str,
    }
)


async def _enumerate_sz(tty: str) -> list[tuple[int, int]]:
    """Return (system, zone) tuples for each system+zone accessible through tty."""
    return [
        (system_id, zone.zone_id)
        for system_id in (1, 2)
        for zone in await BryantEvolutionLocalClient.enumerate_zones(system_id, tty)
    ]


class BryantConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bryant Evolution."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                system_zone = await _enumerate_sz(user_input[CONF_FILENAME])
            except FileNotFoundError:
                _LOGGER.error("Could not open %s: not found", user_input[CONF_FILENAME])
                errors["base"] = "cannot_connect"
            else:
                if len(system_zone) != 0:
                    return self.async_create_entry(
                        title=f"SAM at {user_input[CONF_FILENAME]}",
                        data={
                            CONF_FILENAME: user_input[CONF_FILENAME],
                            CONF_SYSTEM_ZONE: system_zone,
                        },
                    )
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle integration reconfiguration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            system_zone = await _enumerate_sz(user_input[CONF_FILENAME])
            if len(system_zone) != 0:
                our_entry = self.hass.config_entries.async_get_entry(
                    self.context["entry_id"]
                )
                assert our_entry is not None, "Could not find own entry"
                return self.async_update_reload_and_abort(
                    entry=our_entry,
                    data={
                        CONF_FILENAME: user_input[CONF_FILENAME],
                        CONF_SYSTEM_ZONE: system_zone,
                    },
                    unique_id=UNDEFINED,
                    reason="reconfigured",
                )
            errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="reconfigure", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
