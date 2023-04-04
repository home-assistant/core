"""Config flow to configure the Bluetooth integration."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from bluetooth_adapters import (
    ADAPTER_ADDRESS,
    AdapterDetails,
    adapter_human_name,
    adapter_unique_name,
    get_adapters,
)
import voluptuous as vol

from homeassistant.components import onboarding
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import callback
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)
from homeassistant.helpers.typing import DiscoveryInfoType

from . import models
from .const import CONF_ADAPTER, CONF_DETAILS, CONF_PASSIVE, DOMAIN

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSIVE, default=False): bool,
    }
)
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA),
}


class BluetoothConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Bluetooth."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._adapter: str | None = None
        self._details: AdapterDetails | None = None
        self._adapters: dict[str, AdapterDetails] = {}

    async def async_step_integration_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> FlowResult:
        """Handle a flow initialized by discovery."""
        self._adapter = cast(str, discovery_info[CONF_ADAPTER])
        self._details = cast(AdapterDetails, discovery_info[CONF_DETAILS])
        await self.async_set_unique_id(self._details[ADAPTER_ADDRESS])
        self._abort_if_unique_id_configured()
        self.context["title_placeholders"] = {
            "name": adapter_human_name(self._adapter, self._details[ADAPTER_ADDRESS])
        }
        return await self.async_step_single_adapter()

    async def async_step_single_adapter(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select an adapter."""
        adapter = self._adapter
        details = self._details
        assert adapter is not None
        assert details is not None

        address = details[ADAPTER_ADDRESS]

        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=adapter_unique_name(adapter, address), data={}
            )

        return self.async_show_form(
            step_id="single_adapter",
            description_placeholders={"name": adapter_human_name(adapter, address)},
        )

    async def async_step_multiple_adapters(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            assert self._adapters is not None
            adapter = user_input[CONF_ADAPTER]
            address = self._adapters[adapter][ADAPTER_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=adapter_unique_name(adapter, address), data={}
            )

        configured_addresses = self._async_current_ids()
        bluetooth_adapters = get_adapters()
        await bluetooth_adapters.refresh()
        self._adapters = bluetooth_adapters.adapters
        unconfigured_adapters = [
            adapter
            for adapter, details in self._adapters.items()
            if details[ADAPTER_ADDRESS] not in configured_addresses
        ]
        if not unconfigured_adapters:
            ignored_adapters = len(
                self._async_current_entries(include_ignore=True)
            ) - len(self._async_current_entries(include_ignore=False))
            return self.async_abort(
                reason="no_adapters",
                description_placeholders={"ignored_adapters": str(ignored_adapters)},
            )
        if len(unconfigured_adapters) == 1:
            self._adapter = list(self._adapters)[0]
            self._details = self._adapters[self._adapter]
            return await self.async_step_single_adapter()

        return self.async_show_form(
            step_id="multiple_adapters",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADAPTER): vol.In(
                        {
                            adapter: adapter_human_name(
                                adapter, self._adapters[adapter][ADAPTER_ADDRESS]
                            )
                            for adapter in sorted(unconfigured_adapters)
                        }
                    ),
                }
            ),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        return await self.async_step_multiple_adapters()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SchemaOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)

    @classmethod
    @callback
    def async_supports_options_flow(cls, config_entry: ConfigEntry) -> bool:
        """Return options flow support for this handler."""
        return bool(models.MANAGER and models.MANAGER.supports_passive_scan)
