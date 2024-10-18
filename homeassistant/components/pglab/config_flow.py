"""Config flow for PG LAB Electronics integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from .const import DISCOVERY_TOPIC, DOMAIN

CONF_DISCOVERY_PREFIX = "discovery_prefix"


class PGLabFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_mqtt(
        self, discovery_info: MqttServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by MQTT discovery."""

        await self.async_set_unique_id(DOMAIN)

        # Validate the message, abort if it fails.
        if not discovery_info.topic.endswith("/config"):
            # Not a PGLab Electronics discovery message.
            return self.async_abort(reason="invalid_discovery_info")
        if not discovery_info.payload:
            # Empty payload, Unexpected payload.
            return self.async_abort(reason="invalid_discovery_info")

        return await self.async_step_confirm()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        return self.async_abort(reason="not_supported")

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the setup."""

        if user_input is not None:
            return self.async_create_entry(
                title="PG LAB Electronics",
                data={
                    CONF_DISCOVERY_PREFIX: DISCOVERY_TOPIC,
                },
            )

        return self.async_show_form(step_id="confirm")
