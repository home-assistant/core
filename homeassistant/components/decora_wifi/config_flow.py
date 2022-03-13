"""Config flow for Decora WiFi."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class DecoraWifiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Decora WiFi config flow."""

    VERSION = 1
    SCHEMA = vol.Schema(
        {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
    )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Start the user_input flow."""

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=self.SCHEMA)

        await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title="Leviton Decora WiFi", data=user_input)
