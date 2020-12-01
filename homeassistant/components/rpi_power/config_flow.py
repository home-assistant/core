"""Config flow for Raspberry Pi Power Supply Checker."""
from typing import Any, Dict, Optional

from rpi_bad_power import new_under_voltage

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_flow import DiscoveryFlowHandler

from .const import DOMAIN


async def _async_supported(hass: HomeAssistant) -> bool:
    """Return if the system supports under voltage detection."""
    under_voltage = await hass.async_add_executor_job(new_under_voltage)
    return under_voltage is not None


class RPiPowerFlow(DiscoveryFlowHandler, domain=DOMAIN):
    """Discovery flow handler."""

    VERSION = 1

    def __init__(self) -> None:
        """Set up config flow."""
        super().__init__(
            DOMAIN,
            "Raspberry Pi Power Supply Checker",
            _async_supported,
            config_entries.CONN_CLASS_LOCAL_POLL,
        )

    async def async_step_onboarding(
        self, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Handle a flow initialized by onboarding."""
        has_devices = await self._discovery_function(self.hass)

        if not has_devices:
            return self.async_abort(reason="no_devices_found")
        return self.async_create_entry(title=self._title, data={})
