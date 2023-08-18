"""Config flow for Switcher integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_TOKEN, DATA_DISCOVERY, DOMAIN
from .utils import async_discover_devices


class SwitcherFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Switcher config flow."""

    async def _show_setup_form(
        self, errors: dict[str, str] | None = None
    ) -> FlowResult:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_TOKEN): str,
                }
            ),
            errors=errors or {},
        )

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Handle a flow initiated by import."""
        if self._async_current_entries(True):
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(title="Switcher", data={})

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the start of the config flow."""
        if self._async_current_entries(True):
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return await self._show_setup_form(user_input)

        self.hass.data.setdefault(DOMAIN, {})
        if DATA_DISCOVERY not in self.hass.data[DOMAIN]:
            self.hass.data[DOMAIN][DATA_DISCOVERY] = self.hass.async_create_task(
                async_discover_devices()
            )

        return self.async_show_form(step_id="confirm")

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle user-confirmation of the config flow."""
        discovered_devices = await self.hass.data[DOMAIN][DATA_DISCOVERY]

        if user_input is None:
            return await self._show_setup_form(user_input)

        if len(discovered_devices) == 0:
            self.hass.data[DOMAIN].pop(DATA_DISCOVERY)
            return self.async_abort(reason="no_devices_found")

        return self.async_create_entry(
            title="Switcher",
            data={
                CONF_TOKEN: user_input[CONF_TOKEN],
            },
        )
