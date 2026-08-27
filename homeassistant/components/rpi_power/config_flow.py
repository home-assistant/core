"""Config flow for Raspberry Pi Power Supply Checker."""

from collections.abc import Awaitable
from typing import Any, override

from rpi_bad_power import new_under_voltage

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
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
    ) -> ConfigFlowResult:
        """Handle a flow initialized by onboarding."""
        if not await self._discovery_function(self.hass):
            return self.async_abort(reason="not_supported")
        return self.async_create_entry(title=self._title, data={})

    @override
    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setup."""
        if user_input is not None and not await self._discovery_function(self.hass):
            return self.async_abort(reason="not_supported")
        return await super().async_step_confirm(user_input)
