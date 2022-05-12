"""Config flow to configure DSMR Reader."""
from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.components.mqtt import MqttServiceInfo
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


@config_entries.HANDLERS.register(DOMAIN)
class DsmrReaderFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle DSMR Reader config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle user step."""
        if self._async_current_entries():
            return self.async_show_form(
                step_id="user", errors={"base": "single_instance_allowed"}
            )
        if not self.hass.services.has_service(domain="mqtt", service="publish"):
            return self.async_show_form(step_id="user", errors={"base": "mqtt_missing"})
        if user_input is not None:
            return self.async_create_entry(title="DSMR Reader", data={})

        return self.async_show_form(step_id="user")

    async def async_step_mqtt(self, discovery_info: MqttServiceInfo) -> FlowResult:
        """Handle a flow initialized by mqtt discovery."""
        if self._async_in_progress() or self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        await self.async_set_unique_id(DOMAIN)

        # Offer to register all sensors whenever we encounter at least one dsmr/# topic
        return await self.async_step_user()
