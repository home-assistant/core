"""Configure SenseCAP devices across all LoRaWAN connections."""

from typing import Any, override

from homeassistant.components.lorawan import LoRaWANDiscoveryInfo
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class SenseCapConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create one entry for all supported devices."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setup without choosing a server."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return await self.async_step_confirm(user_input)

    @override
    async def async_step_integration_discovery(
        self, discovery_info: LoRaWANDiscoveryInfo | dict[str, Any]
    ) -> ConfigFlowResult:
        """Discover the vendor once across all servers."""
        return await self.async_step_user()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm all supported devices in the selected server applications."""
        if user_input is not None:
            return self.async_create_entry(title="SenseCAP", data={})
        self._set_confirm_only()
        return self.async_show_form(step_id="confirm")
