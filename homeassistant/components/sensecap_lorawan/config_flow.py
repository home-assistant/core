"""Configure SenseCAP devices across all LoRaWAN connections."""

from typing import Any, override

from sensecap_lorawan import SenseCapDeviceCollection

from homeassistant.components.lorawan import (
    LoRaWANDiscoveryInfo,
    NoConnectionsError,
    NoSupportedDevicesError,
    async_validate_devices,
)
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
        device_types = tuple(
            {
                device_type
                for description in DESCRIPTIONS
                for device_type in description.device_types
            }
        )
        try:
            await async_validate_devices(
                self.hass,
                create_collection=SenseCapDeviceCollection,
                is_supported=lambda device: isinstance(device, device_types),
            )
        except NoConnectionsError:
            return self.async_abort(reason="no_lorawan_connections")
        except NoSupportedDevicesError:
            return self.async_abort(reason="no_supported_devices")
        if user_input is not None:
            return self.async_create_entry(title="SenseCAP", data={})
        self._set_confirm_only()
        return self.async_show_form(step_id="confirm")
