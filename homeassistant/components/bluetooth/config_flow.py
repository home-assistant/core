"""Config flow to configure the Bluetooth integration."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components import onboarding
from homeassistant.config_entries import ConfigFlow
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import CONF_ADAPTER, DOMAIN
from .util import async_default_adapter

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult


class BluetoothConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Bluetooth."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._adapter: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        return await self.async_step_default_adapter()

    async def async_step_integration_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> FlowResult:
        """Handle a flow initialized by discovery."""
        adapter = discovery_info[CONF_ADAPTER]
        await self.async_set_unique_id(adapter)
        self._abort_if_unique_id_configured()
        self._adapter = adapter
        self.context["title_placeholders"] = {"name": adapter}
        return await self.async_step_discovered_adapter()

    async def async_step_discovered_adapter(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow for an discovered adapter."""
        adapter = self._adapter
        assert adapter is not None
        if user_input is not None:
            return self.async_create_entry(title=adapter, data={})

        return self.async_show_form(
            step_id="discovered_adapter", description_placeholders={"name": adapter}
        )

    async def async_step_default_adapter(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user or import."""
        adapter = async_default_adapter()
        await self.async_set_unique_id(adapter, raise_on_progress=False)
        self._abort_if_unique_id_configured()

        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            return self.async_create_entry(title=adapter, data={})

        return self.async_show_form(
            step_id="default_adapter", description_placeholders={"name": adapter}
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_default_adapter(user_input)
