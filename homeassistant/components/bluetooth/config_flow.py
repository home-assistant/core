"""Config flow to configure the Bluetooth integration."""

from __future__ import annotations

import platform
from typing import Any, cast

from bluetooth_adapters import (
    ADAPTER_ADDRESS,
    ADAPTER_MANUFACTURER,
    DEFAULT_ADDRESS,
    AdapterDetails,
    adapter_human_name,
    adapter_model,
    get_adapters,
)
from habluetooth import get_manager
import voluptuous as vol

from homeassistant.components import onboarding
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import CONF_ADAPTER, CONF_DETAILS, CONF_PASSIVE, DOMAIN
from .util import adapter_title

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSIVE, default=False): bool,
    }
)
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA),
}


def adapter_display_info(adapter: str, details: AdapterDetails) -> str:
    """Return the adapter display info."""
    name = adapter_human_name(adapter, details[ADAPTER_ADDRESS])
    model = adapter_model(details)
    manufacturer = details[ADAPTER_MANUFACTURER] or "Unknown"
    return f"{name} {manufacturer} {model}"


class BluetoothConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Bluetooth."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._adapter: str | None = None
        self._details: AdapterDetails | None = None
        self._adapters: dict[str, AdapterDetails] = {}
        self._placeholders: dict[str, str] = {}

    async def async_step_integration_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> ConfigFlowResult:
        """Handle a flow initialized by discovery."""
        self._adapter = cast(str, discovery_info[CONF_ADAPTER])
        self._details = cast(AdapterDetails, discovery_info[CONF_DETAILS])
        await self.async_set_unique_id(self._details[ADAPTER_ADDRESS])
        self._abort_if_unique_id_configured()
        details = self._details
        self._async_set_adapter_info(self._adapter, details)
        return await self.async_step_single_adapter()

    @callback
    def _async_set_adapter_info(self, adapter: str, details: AdapterDetails) -> None:
        """Set the adapter info."""
        name = adapter_human_name(adapter, details[ADAPTER_ADDRESS])
        model = adapter_model(details)
        manufacturer = details[ADAPTER_MANUFACTURER]
        self._placeholders = {
            "name": name,
            "model": model,
            "manufacturer": manufacturer or "Unknown",
        }
        self.context["title_placeholders"] = self._placeholders

    async def async_step_single_adapter(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select an adapter."""
        adapter = self._adapter
        details = self._details
        assert adapter is not None
        assert details is not None
        assert self._placeholders is not None

        address = details[ADAPTER_ADDRESS]

        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=adapter_title(adapter, details), data={}
            )

        return self.async_show_form(
            step_id="single_adapter",
            description_placeholders=self._placeholders,
        )

    async def async_step_multiple_adapters(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            assert self._adapters is not None
            adapter = user_input[CONF_ADAPTER]
            details = self._adapters[adapter]
            address = details[ADAPTER_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=adapter_title(adapter, details), data={}
            )

        configured_addresses = self._async_current_ids()
        bluetooth_adapters = get_adapters()
        await bluetooth_adapters.refresh()
        self._adapters = bluetooth_adapters.adapters
        system = platform.system()
        unconfigured_adapters = [
            adapter
            for adapter, details in self._adapters.items()
            if details[ADAPTER_ADDRESS] not in configured_addresses
            # DEFAULT_ADDRESS is perfectly valid on MacOS but on
            # Linux it means the adapter is not yet configured
            # or crashed
            and not (system == "Linux" and details[ADAPTER_ADDRESS] == DEFAULT_ADDRESS)
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
            self._async_set_adapter_info(self._adapter, self._details)
            return await self.async_step_single_adapter()

        return self.async_show_form(
            step_id="multiple_adapters",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADAPTER): vol.In(
                        {
                            adapter: adapter_display_info(
                                adapter, self._adapters[adapter]
                            )
                            for adapter in sorted(unconfigured_adapters)
                        }
                    ),
                }
            ),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
        return bool((manager := get_manager()) and manager.supports_passive_scan)
