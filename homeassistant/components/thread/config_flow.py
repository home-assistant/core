"""Config flow for the Thread integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components import onboarding
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN


class ThreadConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Thread."""

    VERSION = 1

    async def async_step_import(self, import_data: None) -> ConfigFlowResult:
        """Set up by import from async_setup."""
        await self._async_handle_discovery_without_unique_id()
        return self.async_create_entry(title="Thread", data={})

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Set up by import from async_setup."""
        await self._async_handle_discovery_without_unique_id()
        return self.async_create_entry(title="Thread", data={})

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Set up because the user has border routers."""
        await self._async_handle_discovery_without_unique_id()
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the setup."""
        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            return self.async_create_entry(title="Thread", data={})
        return self.async_show_form(step_id="confirm")
