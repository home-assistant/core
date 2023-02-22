"""Config flow for the Thread integration."""
from __future__ import annotations

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class ThreadConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Thread."""

    VERSION = 1

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Set up because the user has border routers."""
        await self._async_handle_discovery_without_unique_id()
        return self.async_create_entry(title="Thread", data={})

    async def async_step_import(
        self, import_data: dict[str, str] | None = None
    ) -> FlowResult:
        """Set up by import from async_setup."""
        await self._async_handle_discovery_without_unique_id()
        return self.async_create_entry(title="Thread", data={})
