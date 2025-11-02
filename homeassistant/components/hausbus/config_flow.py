"""Config flow for Haus-Bus integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pyhausbus.HomeServer import HomeServer
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)

DEVICE_SEARCH_TIMEOUT = 5
STEP_USER_SCHEMA = vol.Schema({})


class ConfigFlow(IBusDataListener, config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Haus-Bus."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._search_task: asyncio.Task | None = None
        self.home_server: HomeServer = HomeServer()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            await self.async_set_unique_id("42")
            self._abort_if_unique_id_configured()
            return self.async_show_progress_done(next_step_id="search_complete")

        errors: dict[str, str] = {}
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_search_complete(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create a configuration entry for the Haus-Bus devices."""
        return self.async_create_entry(title="Haus-Bus", data={})

    async def async_step_discovery(self, discovery_info=None):
        """Handle discovery of Haus-Bus devices."""
        entries = self.hass.config_entries.async_entries(DOMAIN)
        if not entries:
            LOGGER.debug("No Haus-Bus config entries found, cannot discover devices")
            return self.async_abort(reason="no_config_entry")

        gateway = entries[0].runtime_data

        try:
            LOGGER.debug("Running device discovery via async_step_discovery")
            gateway.home_server.searchDevices()
        except Exception as err:
            raise HomeAssistantError(f"Failed to discover devices: {err}") from err

        return self.async_create_entry(
            title="Haus-Bus Devices Discovered", data={"discovered": True}
        )