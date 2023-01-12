"""Config flow for the Open Thread Border Router integration."""
from __future__ import annotations

from homeassistant.components.hassio import HassioServiceInfo
from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class OTBRConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Home Assistant Sky Connect."""

    VERSION = 1

    async def async_step_hassio(self, discovery_info: HassioServiceInfo) -> FlowResult:
        """Handle hassio discovery."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        config = discovery_info.config
        return self.async_create_entry(
            title="Thread",
            data={"url": f"http://{config['host']}:{config['port']}"},
        )
