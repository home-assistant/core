"""Config flow for Tasmota."""
from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo, ReceivePayloadType

from .const import CONF_DISCOVERY_PREFIX, DISCOVERY_TOPIC, DOMAIN


class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._prefix = DISCOVERY_TOPIC
        self._payload: ReceivePayloadType = ""

    async def async_step_mqtt(self, discovery_info: MqttServiceInfo) -> FlowResult:
        """Handle a flow initialized by MQTT discovery."""
        if self._async_in_progress() or self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        await self.async_set_unique_id(DOMAIN)

        # Validate the message, abort if it fails
        if not discovery_info.topic.endswith("/config"):
            # Not a PG LAB Electronics discovery message
            return self.async_abort(reason="invalid_discovery_info")
        if not discovery_info.payload:
            # Empty payload, unexpesd payload
            return self.async_abort(reason="invalid_discovery_info")

        # "pglab/discovery/#" is hardcoded in manifest.json
        assert discovery_info.subscribed_topic == "pglab/discovery/#"
        self._prefix = "pglab/discovery"
        self._payload = discovery_info.payload

        return await self.async_step_confirm()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm the setup."""

        data = {
            CONF_DISCOVERY_PREFIX: self._prefix,
        }

        if user_input is not None:
            return self.async_create_entry(title="PG LAB Electronics", data=data)

        return self.async_show_form(step_id="confirm")
