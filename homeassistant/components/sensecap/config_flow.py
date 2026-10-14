"""Configure SenseCAP devices across all LoRaWAN connections."""

from typing import Any, override

from lorawan_connection import ConnectionUnavailable
from sensecap_lorawan import SenseCapDeviceCollection

from homeassistant.components.lorawan import LoRaWANDiscoveryInfo, async_get_connections
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN
from .sensor import DESCRIPTIONS


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
        if reason := await self._async_check_devices():
            return self.async_abort(reason=reason)
        if user_input is not None:
            return self.async_create_entry(title="SenseCAP", data={})
        self._set_confirm_only()
        return self.async_show_form(step_id="confirm")

    async def _async_check_devices(self) -> str | None:
        """Require a connection with a model supported by the sensor platform."""
        if not (connections := async_get_connections(self.hass)):
            return "no_lorawan_connections"
        device_types = tuple({description.device_type for description in DESCRIPTIONS})
        reason = "no_supported_devices"
        for connection in connections:
            collection = SenseCapDeviceCollection(connection)
            try:
                await collection.async_setup()
                if any(
                    isinstance(device, device_types)
                    for device in collection.devices.values()
                ):
                    return None
            except ConnectionUnavailable:
                reason = "cannot_connect"
            finally:
                collection.close()
        return reason
