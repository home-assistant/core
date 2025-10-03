"""Config flow for iNELS."""

from __future__ import annotations

from typing import Any

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from .const import DOMAIN, TITLE


class INelsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle of iNELS config flow."""

    VERSION = 1

    async def async_step_mqtt(
        self, discovery_info: MqttServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by MQTT discovery."""
        if self._async_in_progress() or self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        # Validate the message, abort if it fails.
        if not discovery_info.topic.endswith("/gw"):
            # Not an iNELS discovery message.
            return self.async_abort(reason="invalid_discovery_info")
        if not discovery_info.payload:
            # Empty payload, unexpected payload.
            return self.async_abort(reason="invalid_discovery_info")

        return await self.async_step_confirm_from_mqtt()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        # There is no reason to have multiple entries due to the single broker limitation
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        try:
            if not mqtt.is_connected(self.hass):
                return self.async_abort(reason="mqtt_not_connected")
        except KeyError:
            return self.async_abort(reason="mqtt_not_configured")

        return await self.async_step_confirm_from_user()

    async def step_confirm(
        self, step_id: str, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the setup."""

        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=TITLE, data={})

        return self.async_show_form(step_id=step_id)

    async def async_step_confirm_from_mqtt(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the setup from MQTT discovered."""
        return await self.step_confirm(
            step_id="confirm_from_mqtt", user_input=user_input
        )

    async def async_step_confirm_from_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the setup from user add integration."""
        return await self.step_confirm(
            step_id="confirm_from_user", user_input=user_input
        )
