"""Config flow for WeatherFlow."""
from __future__ import annotations

import asyncio
from asyncio import Future
from typing import Any

# import my_pypi_dependency
from pyweatherflowudp.client import EVENT_DEVICE_DISCOVERED, WeatherFlowListener
from pyweatherflowudp.const import DEFAULT_HOST
from pyweatherflowudp.errors import AddressInUseError, ListenerError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST, default=DEFAULT_HOST): str})


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if there are devices that can be discovered."""

    future_event: Future[bool] = asyncio.Future()
    host: str = DEFAULT_HOST

    @callback
    def found():
        """Handle a discovered device."""
        future_event.set_result(True)

    async with WeatherFlowListener(host) as client:
        LOGGER.debug("Registering EVENT_DISCOVERED_FUNCTION")
        try:
            client.on(EVENT_DEVICE_DISCOVERED, lambda _: found())
            await asyncio.wait_for(future_event, timeout=10)
        except asyncio.TimeoutError:
            return False
    return True


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WeatherFlow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""

        # Only allow a single instance of integration
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            host = DEFAULT_HOST
        else:
            host = user_input.get(CONF_HOST)

        # Get current discovered entries.
        in_progress = self._async_in_progress()

        if not (has_devices := in_progress):
            errors = {}
            try:
                has_devices = await _async_has_devices(host)  # type: ignore[assignment]

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
            data=user_input or {CONF_HOST: DEFAULT_HOST},
        )
