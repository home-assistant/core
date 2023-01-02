"""Config flow for Raspberry Pi Power Supply Checker."""
from __future__ import annotations

from collections.abc import Awaitable
from typing import Any

from rpi_bad_power import new_under_voltage

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.config_entry_flow import DiscoveryFlowHandler

from .const import DOMAIN


async def _async_supported(hass: HomeAssistant) -> bool:
    """Return if the system supports under voltage detection."""
    under_voltage = await hass.async_add_executor_job(new_under_voltage)
    return under_voltage is not None


class RPiPowerFlow(DiscoveryFlowHandler[Awaitable[bool]], domain=DOMAIN):
    """Discovery flow handler."""

    VERSION = 1

    def __init__(self) -> None:
        """Set up config flow."""
        super().__init__(
            DOMAIN,
            "Raspberry Pi Power Supply Checker",
            _async_supported,
        )

    async def async_step_onboarding(
        self, data: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by onboarding."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        has_devices = await self._discovery_function(self.hass)

        if not has_devices:
            return self.async_abort(reason="no_devices_found")
        return self.async_create_entry(title=self._title, data={})
