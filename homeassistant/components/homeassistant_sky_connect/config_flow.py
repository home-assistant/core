"""Config flow for the Home Assistant SkyConnect integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components import usb
from homeassistant.components.homeassistant_hardware import silabs_multiprotocol_addon
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN
from .util import get_usb_service_info


class HomeAssistantSkyConnectConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Home Assistant SkyConnect."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> HomeAssistantSkyConnectOptionsFlow:
        """Return the options flow."""
        return HomeAssistantSkyConnectOptionsFlow(config_entry)

    async def async_step_usb(self, discovery_info: usb.UsbServiceInfo) -> FlowResult:
        """Handle usb discovery."""
        device = discovery_info.device
        vid = discovery_info.vid
        pid = discovery_info.pid
        serial_number = discovery_info.serial_number
        manufacturer = discovery_info.manufacturer
        description = discovery_info.description
        unique_id = f"{vid}:{pid}_{serial_number}_{manufacturer}_{description}"
        if await self.async_set_unique_id(unique_id):
            self._abort_if_unique_id_configured(updates={"device": device})
        return self.async_create_entry(
            title="Home Assistant SkyConnect",
            data={
                "device": device,
                "vid": vid,
                "pid": pid,
                "serial_number": serial_number,
                "manufacturer": manufacturer,
                "description": description,
            },
        )


class HomeAssistantSkyConnectOptionsFlow(silabs_multiprotocol_addon.OptionsFlowHandler):
    """Handle an option flow for Home Assistant SkyConnect."""

    async def _async_serial_port_settings(
        self,
    ) -> silabs_multiprotocol_addon.SerialPortSettings:
        """Return the radio serial port settings."""
        usb_dev = self.config_entry.data["device"]
        dev_path = await self.hass.async_add_executor_job(usb.get_serial_by_id, usb_dev)
        return silabs_multiprotocol_addon.SerialPortSettings(
            device=dev_path,
            baudrate="115200",
            flow_control=True,
        )

    async def _async_zha_physical_discovery(self) -> dict[str, Any]:
        """Return ZHA discovery data when multiprotocol FW is not used.

        Passed to ZHA do determine if the ZHA config entry is connected to the radio
        being migrated.
        """
        return {"usb": get_usb_service_info(self.config_entry)}

    def _zha_name(self) -> str:
        """Return the ZHA name."""
        return "SkyConnect Multi-PAN"

    def _hardware_name(self) -> str:
        """Return the name of the hardware."""
        return "Home Assistant SkyConnect"
