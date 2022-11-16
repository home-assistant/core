"""Config flow for the Home Assistant Yellow integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.homeassistant_hardware import silabs_multiprotocol_addon
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class HomeAssistantYellowConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Home Assistant Yellow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> HomeAssistantYellowOptionsFlow:
        """Return the options flow."""
        return HomeAssistantYellowOptionsFlow(config_entry)

    async def async_step_system(self, data: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(title="Home Assistant Yellow", data={})


class HomeAssistantYellowOptionsFlow(silabs_multiprotocol_addon.OptionsFlowHandler):
    """Handle an option flow for Home Assistant Yellow."""

    async def _async_serial_port_settings(
        self,
    ) -> silabs_multiprotocol_addon.SerialPortSettings:
        """Return the radio serial port settings."""
        return silabs_multiprotocol_addon.SerialPortSettings(
            device="/dev/ttyAMA1",
            baudrate="115200",
            flow_control=True,
        )
