"""Config flow for Coronavirus integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from . import get_coordinator
from .const import DOMAIN, OPTION_WORLDWIDE


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Coronavirus."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    _options = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if self._options is None:
            coordinator = await get_coordinator(self.hass)
            if not coordinator.last_update_success or coordinator.data is None:
                return self.async_abort(reason="cannot_connect")

            self._options = {OPTION_WORLDWIDE: "Worldwide"}
            for case in sorted(
                coordinator.data.values(), key=lambda case: case.country
            ):
                self._options[case.country] = case.country

        if user_input is not None:
            await self.async_set_unique_id(user_input["country"])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._options[user_input["country"]], data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("country"): vol.In(self._options)}),
            errors=errors,
        )
