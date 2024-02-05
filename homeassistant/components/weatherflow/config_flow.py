"""Config flow for WeatherFlow."""
from __future__ import annotations

import asyncio
from asyncio import Future
from asyncio.exceptions import CancelledError
from typing import Any

from pyweatherflowudp.client import EVENT_DEVICE_DISCOVERED, WeatherFlowListener
from pyweatherflowudp.errors import AddressInUseError, EndpointError, ListenerError

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    ERROR_MSG_ADDRESS_IN_USE,
    ERROR_MSG_CANNOT_CONNECT,
    ERROR_MSG_NO_DEVICE_FOUND,
)


async def _async_can_discover_devices() -> bool:
    """Return if there are devices that can be discovered."""
    future_event: Future[None] = asyncio.get_running_loop().create_future()

    @callback
    def _async_found(_):
        """Handle a discovered device - only need to do this once so."""

        if not future_event.done():
            future_event.set_result(None)

    async with WeatherFlowListener() as client, asyncio.timeout(10):
        try:
            client.on(EVENT_DEVICE_DISCOVERED, _async_found)
            await future_event
        except TimeoutError:
            return False

    return True


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WeatherFlow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""

        # Only allow a single instance of integration since the listener
        # will pick up all devices on the network and we don't want to
        # create multiple entries.
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        found = False
        errors = {}
        try:
            found = await _async_can_discover_devices()
        except AddressInUseError:
            errors["base"] = ERROR_MSG_ADDRESS_IN_USE
        except (ListenerError, EndpointError, CancelledError):
            errors["base"] = ERROR_MSG_CANNOT_CONNECT

        if not found and not errors:
            errors["base"] = ERROR_MSG_NO_DEVICE_FOUND

        if errors:
            return self.async_show_form(step_id="user", errors=errors)

        return self.async_create_entry(title="WeatherFlow", data={})
