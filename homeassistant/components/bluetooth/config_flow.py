"""Config flow to configure the Bluetooth integration."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components import onboarding
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback

from .const import CONF_ADAPTER, DEFAULT_NAME, DOMAIN
from .util import async_get_bluetooth_adapters

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult


class BluetoothConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Bluetooth."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        return await self.async_step_enable_bluetooth()

    async def async_step_enable_bluetooth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user or import."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            return self.async_create_entry(title=DEFAULT_NAME, data={})

        return self.async_show_form(step_id="enable_bluetooth")

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_enable_bluetooth(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(OptionsFlow):
    """Handle the option flow for bluetooth."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        if not (adapters := await async_get_bluetooth_adapters()):
            return self.async_abort(reason="no_adapters")

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_ADAPTER,
                    default=self.config_entry.options.get(CONF_ADAPTER, adapters[0]),
                ): vol.In(adapters),
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)
