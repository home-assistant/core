"""Config flow for Fast.com integration."""
from __future__ import annotations

import random
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_INTERVAL, DOMAIN


class FastdotcomConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fast.com."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        if user_input is not None:
            await self.async_set_unique_id(DOMAIN + str(random.randint(0, 100000)))
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Fast.com",
                data={},
                options={CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL]},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_INTERVAL): vol.All(
                        vol.Coerce(int), vol.Range(min=1)
                    ),
                }
            ),
        )
