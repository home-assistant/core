"""Config flow to configure DSMR Reader."""
from __future__ import annotations

from collections.abc import Awaitable
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.config_entry_flow import DiscoveryFlowHandler

from .const import DOMAIN


async def _async_has_devices(_: HomeAssistant) -> bool:
    """Return true as this integration doesn't support any real devices."""
    return True


class DsmrReaderFlowHandler(DiscoveryFlowHandler[Awaitable[bool]], domain=DOMAIN):
    """Handle DSMR Reader config flow. The MQTT step is inherited from the parent class."""

    VERSION = 1

    def __init__(self) -> None:
        """Set up the config flow."""
        super().__init__(DOMAIN, "DSMR Reader", _async_has_devices)

    async def async_step_import(self, _: dict[str, Any] | None) -> FlowResult:
        """Import from configuration.yaml and create config entry."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        # There's no configuration supported for this integration, so data can be a fixed object
        return self.async_create_entry(title="DSMR Reader", data={})

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle user step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if not self.hass.services.has_service(domain="mqtt", service="publish"):
            return self.async_show_form(
                step_id="confirm", errors={"base": "mqtt_missing"}
            )

        return await self.async_step_confirm()
