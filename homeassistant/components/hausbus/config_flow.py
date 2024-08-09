"""Config flow for Haus-Bus integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pyhausbus.BusDataMessage import BusDataMessage
from pyhausbus.de.hausbus.homeassistant.proxy.controller.data.ModuleId import ModuleId
from pyhausbus.HomeServer import HomeServer
from pyhausbus.IBusDataListener import IBusDataListener
from pyhausbus.ObjectId import ObjectId
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema({})


class ConfigFlow(IBusDataListener, config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[misc]
    """Handle a config flow for hausbus."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._found_device = False
        self._search_task: asyncio.Task | None = None
        self.home_server = HomeServer()
        self.home_server.addBusEventListener(self)

    def remove_bus_event_listeners(self) -> None:
        """Cleanup after finishing the config flow."""
        self.home_server.removeBusEventListener(self)
        self.home_server.removeBusEventListener(self.home_server)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # start searching for devices
            return await self.async_step_wait_for_device()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_wait_for_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Wait for a hausbus device to be found."""
        if not self._search_task:
            self._search_task = self.hass.async_create_task(
                self._async_wait_for_device()
            )

        if not self._search_task.done():
            return self.async_show_progress(
                step_id="wait_for_device",
                progress_action="wait_for_device",
                progress_task=self._search_task,
            )

        try:
            await self._search_task
        except TimeoutError:
            return self.async_show_progress_done(next_step_id="search_timeout")
        finally:
            self._search_task = None

        return self.async_show_progress_done(next_step_id="search_complete")

    async def async_step_search_timeout(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Inform the user that no device has been found."""
        if user_input is not None:
            return await self.async_step_wait_for_device()

        return self.async_show_form(step_id="search_timeout")

    async def async_step_search_complete(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create a configuration entry for the hausbus devices."""
        self.remove_bus_event_listeners()
        return self.async_create_entry(title="Haus-Bus", data={})

    async def _async_wait_for_device(self) -> None:
        """Start searching for devices and wait until at least one device was found or timeout is reached."""
        self.home_server.searchDevices()
        # wait for up to 5 seconds to find devices
        await asyncio.wait_for(self._check_device_found(), 5)

    async def _check_device_found(self) -> bool:
        """Check if a device was found periodically."""
        while not self._found_device:
            await asyncio.sleep(0.1)  # Poll every 0.1 seconds
        return True

    def busDataReceived(self, busDataMessage: BusDataMessage) -> None:
        """Handle Haus-Bus messages."""
        object_id = ObjectId(busDataMessage.getSenderObjectId())
        data = busDataMessage.getData()

        if object_id.getDeviceId() == 9998:
            # ignore messages sent from this module
            return

        if isinstance(data, ModuleId):
            # module ID of a Haus-Bus device was received
            self._found_device = True
