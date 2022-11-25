"""Config flow for the Home Assistant Sky Connect integration."""
from __future__ import annotations

from homeassistant.components import usb
from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class HomeAssistantSkyConnectConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Home Assistant Sky Connect."""

    VERSION = 1

    async def async_step_usb(self, discovery_info: usb.UsbServiceInfo) -> FlowResult:
        """Handle usb discovery."""
        if await self.async_set_unique_id(usb.generate_unique_id(discovery_info)):
            self._abort_if_unique_id_configured(
                updates={"device": discovery_info.device}
            )
        return self.async_create_entry(
            title="Home Assistant Sky Connect",
            data={
                "device": discovery_info.device,
                "vid": discovery_info.vid,
                "pid": discovery_info.pid,
                "serial_number": discovery_info.serial_number,
                "manufacturer": discovery_info.manufacturer,
                "description": discovery_info.description,
            },
        )
