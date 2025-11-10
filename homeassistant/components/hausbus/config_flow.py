"""Config flow for Haus-Bus integration."""
 
from __future__ import annotations

import asyncio
import logging
from typing import Any

from pyhausbus.HomeServer import HomeServer
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema({})


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for hausbus."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._search_task: asyncio.Task | None = None
        self.home_server = HomeServer()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            # start searching for devices
            return await self.async_step_wait_for_device()

        errors: dict[str, str] = {}
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_wait_for_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Wait for a hausbus device to be found."""
        if not self._search_task:
            self._search_task = self.hass.async_create_task(
                self._async_wait_for_device()
            )

        if not self._search_task.done():
            return self.async_show_progress(
                step_id="wait_for_device",
                progress_action="searching devices",
                progress_task=self._search_task,
            )

        try:
            await self._search_task
        except TimeoutError:
            if self._search_task:
                self._search_task.cancel()
            return self.async_show_progress_done(next_step_id="search_timeout")
        finally:
            self._search_task = None

        return self.async_show_progress_done(next_step_id="search_complete")

    async def async_step_search_timeout(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Inform the user that no device has been found."""
        if user_input is not None:
            return await self.async_step_wait_for_device()

        return self.async_show_form(step_id="search_timeout")

    async def async_step_search_complete(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Create a configuration entry for the hausbus devices."""
        return self.async_create_entry(title="Haus-Bus", data={})

    async def _async_wait_for_device(self) -> None:
        """Start searching for devices and wait until at least one device was found or timeout is reached."""
        await self.hass.async_add_executor_job(self.home_server.searchDevices)
        # wait for up to 5 seconds to find devices
        await asyncio.wait_for(self._check_device_found(), 5)

    async def _check_device_found(self) -> bool:
        """Check if a device was found periodically."""
        while not self.home_server.is_any_device_found():
            await asyncio.sleep(0.1)  # Poll every 0.1 seconds
        return True
