"""Config flow for baf."""
from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN
from .models import BAFDiscovery

API_SUFFIX = "._api._tcp.local."


class BAFFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle BAF discovery config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the BAF config flow."""
        self.discovery: BAFDiscovery | None = None

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        name = discovery_info.name
        if name.endswith(API_SUFFIX):
            name = name[: -len(API_SUFFIX)]
        properties = discovery_info.properties
        ip_address = discovery_info.host
        uuid = properties["uuid"]
        model = properties["model"]
        await self.async_set_unique_id(uuid, raise_on_progress=False)
        self._abort_if_unique_id_configured(updates={CONF_IP_ADDRESS: ip_address})
        self.discovery = BAFDiscovery(name, ip_address, uuid, model)
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        assert self.discovery is not None
        discovery = self.discovery
        if user_input is not None:
            return await self._async_entry_for_discovered_device(discovery)
        placeholders = {
            "name": discovery.name,
            "model": discovery.model,
            "ip_address": discovery.ip_address,
        }
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders=placeholders
        )

    async def _async_entry_for_discovered_device(
        self, discovery: BAFDiscovery
    ) -> FlowResult:
        """Create a config entry for a device."""
        return self.async_create_entry(
            title=discovery.name,
            data={CONF_IP_ADDRESS: discovery.ip_address},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        raise NotImplementedError
