"""Config flow for WeatherFlow."""
from __future__ import annotations

import asyncio
from typing import Any

from async_timeout import timeout

# import my_pypi_dependency
from pyweatherflowudp.client import EVENT_DEVICE_DISCOVERED, WeatherFlowListener
from pyweatherflowudp.const import DEFAULT_HOST
from pyweatherflowudp.errors import AddressInUseError, ListenerError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_flow

from .const import DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if there are devices that can be discovered."""

    event = asyncio.Event()
    host: str = DEFAULT_HOST

    @callback
    def found():
        """Handle a discovered device."""
        event.set()

    async with WeatherFlowListener(host) as client:
        LOGGER.info("Registering EVENT_DISCOVERED_FUNCTION")
        client.on(EVENT_DEVICE_DISCOVERED, lambda _: found())
        try:
            async with timeout(10):
                await event.wait()
        except asyncio.TimeoutError:
            return False
    return True


config_entry_flow.register_discovery_flow(DOMAIN, "WeatherFlow", _async_has_devices)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WeatherFlow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        current_hosts = [
            entry.data.get(CONF_HOST, DEFAULT_HOST)
            for entry in self._async_current_entries()
        ]

        if user_input is None:
            if DEFAULT_HOST in current_hosts:
                return self.async_show_form(
                    step_id="user", data_schema=STEP_USER_DATA_SCHEMA
                )
            host = DEFAULT_HOST
        else:
            host = user_input.get(CONF_HOST)

        if host in current_hosts:
            return self.async_abort(reason="single_instance_allowed")

        # Get current discovered entries.
        in_progress = self._async_in_progress()

        if not (has_devices := in_progress):
            errors = {}
            try:
                has_devices = await self.hass.async_add_job(_async_has_devices, host)  # type: ignore[arg-type, misc]
            except AddressInUseError:
                errors["base"] = "address_in_use"
            except ListenerError:
                errors["base"] = "cannot_connect"

            if errors or (not has_devices and user_input is None):
                return self.async_show_form(
                    step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
                )

        if not has_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_create_entry(
            title=f"WeatherFlow{f' ({host})' if host != DEFAULT_HOST else ''}",
            data=user_input or {},
        )
