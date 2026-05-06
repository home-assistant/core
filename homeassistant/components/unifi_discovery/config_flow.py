"""Config flow for UniFi Discovery."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .const import DOMAIN
from .discovery import async_start_discovery

_LOGGER = logging.getLogger(__name__)


class UnifiDiscoveryFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for UniFi Discovery."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a user-initiated flow."""
        async_start_discovery(self.hass)
        return self.async_abort(reason="discovery_started")

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovery via DHCP."""
        _LOGGER.debug("Starting discovery via DHCP: %s", discovery_info)
        if self._async_in_progress():
            return self.async_abort(reason="already_in_progress")
        async_start_discovery(self.hass)
        return self.async_abort(reason="discovery_started")

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovery via SSDP."""
        _LOGGER.debug("Starting discovery via SSDP: %s", discovery_info)
        if self._async_in_progress():
            return self.async_abort(reason="already_in_progress")
        async_start_discovery(self.hass)
        return self.async_abort(reason="discovery_started")
