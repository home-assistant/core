"""Config flow for LIFX."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN
from .discovery import LifxNetworkScanner

if TYPE_CHECKING:
    import asyncio

_LOGGER = logging.getLogger(__name__)


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if there are devices that can be discovered."""
    lifx_network_scanner = LifxNetworkScanner(hass=hass)
    return await lifx_network_scanner.found_lifx_devices()


class LifxConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle LIFX config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the LIFX config flow."""
        self._domain = DOMAIN
        self._title = "LIFX"
        self._discovery_function = _async_has_devices

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        await self.async_set_unique_id(self._domain, raise_on_progress=False)
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm setup."""
        if user_input is None:
            self._set_confirm_only()
            return self.async_show_form(step_id="confirm")

        if self.source == config_entries.SOURCE_USER:
            # Get current discovered entries.
            in_progress = self._async_in_progress()

            if not (has_devices := bool(in_progress)):
                has_devices = await cast(
                    "asyncio.Future[bool]",
                    self.hass.async_add_job(self._discovery_function, self.hass),
                )

            if not has_devices:
                return self.async_abort(reason="no_devices_found")

            # Cancel the discovered one.
            for flow in in_progress:
                self.hass.config_entries.flow.async_abort(flow["flow_id"])

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(title=self._title, data={})

    async def async_step_homekit(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Trigger local discovery from HomeKit mDNS."""
        if self._async_in_progress() or self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if await _async_has_devices(self.hass) is False:
            _LOGGER.debug("LIFX discovery failed, no devices found")
            return self.async_abort(reason="no_devices_found")

        _LOGGER.debug("LIFX discovery found devices, creating config entry")
        await self.async_set_unique_id(self._domain)

        return await self.async_step_confirm()
