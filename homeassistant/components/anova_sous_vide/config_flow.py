"""Config flow for Anova."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class AnovaConfligFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Sets up a config flow for Anova."""

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        if user_input is not None:
            entries = self._async_current_entries()
            if any(x.data["device_id"] == user_input["device_id"] for x in entries):
                return self.async_abort(reason="already_configured")

            await self.async_set_unique_id(user_input["device_id"])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Anova Sous Vide", data={"device_id": user_input["device_id"]}
            )

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({vol.Required("device_id"): str})
        )

    async def async_step_import(self, import_config: dict[str, str]) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        entries = self._async_current_entries()
        if any(x.data["device_id"] == import_config["device_id"] for x in entries):
            return self.async_abort(reason="already_configured")
        return await self.async_step_user(import_config)
