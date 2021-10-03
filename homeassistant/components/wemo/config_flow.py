"""Config flow for Wemo."""

from __future__ import annotations

from typing import Any

import pywemo

from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.config_entry_flow import DiscoveryFlowHandler

from .const import DOMAIN
from .wemo_device import Options


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if there are devices that can be discovered."""
    return bool(await hass.async_add_executor_job(pywemo.discover_devices))


class WemoFlow(DiscoveryFlowHandler, domain=DOMAIN):
    """Discovery flow with options for Wemo."""

    def __init__(self) -> None:
        """Init discovery flow."""
        super().__init__(DOMAIN, "Wemo", _async_has_devices)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return WemoOptionsFlow(config_entry)


class WemoOptionsFlow(OptionsFlow):
    """Options flow for the WeMo component."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options for the WeMo component."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=Options(**self.config_entry.options).schema(),
        )
