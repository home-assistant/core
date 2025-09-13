"""Config flow for Haus-Bus integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pyhausbus.BusDataMessage import BusDataMessage
from pyhausbus.de.hausbus.homeassistant.proxy.controller.data.ModuleId import ModuleId
from pyhausbus.HausBusUtils import HOMESERVER_DEVICE_ID
from pyhausbus.HomeServer import HomeServer
from pyhausbus.IBusDataListener import IBusDataListener
from pyhausbus.ObjectId import ObjectId
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
        self._found_device: bool = False
        self._search_task: asyncio.Task | None = None
        self.home_server: HomeServer = HomeServer()
        self.home_server.addBusEventListener(self)

    def remove_bus_event_listeners(self) -> None:
        """Cleanup after finishing the config flow."""
        self.home_server.removeBusEventListener(self)

    def async_remove(self) -> None:
        """Trigger cleanup of bus event listeners after config flow."""
        self.remove_bus_event_listeners()
        return super().async_remove()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            await self.async_set_unique_id("42")
            self._abort_if_unique_id_configured()
            return await self.async_step_wait_for_device()

        errors: dict[str, str] = {}
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_wait_for_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Wait for a Haus-Bus device to be found."""
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
        """Create a configuration entry for the Haus-Bus devices."""
        return self.async_create_entry(title="Haus-Bus", data={})

    async def _async_wait_for_device(self) -> None:
        """Start searching for devices and wait until at least one device is found or timeout is reached."""
        self.hass.async_add_executor_job(self.home_server.searchDevices)
        await asyncio.wait_for(self._check_device_found(), DEVICE_SEARCH_TIMEOUT)

    async def _check_device_found(self) -> bool:
        """Check periodically if a device was found."""
        while not self._found_device:
            await asyncio.sleep(0.1)
        return True

    async def async_step_discovery(self, discovery_info=None):
        """Handle discovery of Haus-Bus devices."""
        entries = self.hass.config_entries.async_entries(DOMAIN)
        if not entries:
            LOGGER.debug("No Haus-Bus config entries found, cannot discover devices")
            return self.async_abort(reason="no_config_entry")

        gateway = entries[0].runtime_data.gateway

        try:
            LOGGER.debug("Running device discovery via async_step_discovery")
            gateway.home_server.searchDevices()
        except Exception as err:
            raise HomeAssistantError(f"Failed to discover devices: {err}") from err

        return self.async_create_entry(
            title="Haus-Bus Devices Discovered", data={"discovered": True}
        )

    def busDataReceived(self, busDataMessage: BusDataMessage) -> None:
        """Handle Haus-Bus messages."""
        object_id = ObjectId(busDataMessage.getSenderObjectId())
        data = busDataMessage.getData()

        if object_id.getDeviceId() == HOMESERVER_DEVICE_ID:
            return  # ignore messages from this module

        if isinstance(data, ModuleId):
            # module ID of a Haus-Bus device was received
            self._found_device = True
