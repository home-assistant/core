"""Config flow for Tasmota."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.mqtt import valid_subscribe_topic
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from .const import CONF_DISCOVERY_PREFIX, DEFAULT_PREFIX, DOMAIN


class FlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._prefix = DEFAULT_PREFIX

    async def async_step_mqtt(
        self, discovery_info: MqttServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by MQTT discovery."""
        if self._async_in_progress() or self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        await self.async_set_unique_id(DOMAIN)

        # Validate the message, abort if it fails
        if not discovery_info.topic.endswith("/config"):
            # Not a Tasmota discovery message
            return self.async_abort(reason="invalid_discovery_info")
        if not discovery_info.payload:
            # Empty payload, the Tasmota is not configured for native discovery
            return self.async_abort(reason="invalid_discovery_info")

        # "tasmota/discovery/#" is hardcoded in Tasmota's manifest
        assert discovery_info.subscribed_topic == "tasmota/discovery/#"
        self._prefix = "tasmota/discovery"

        return await self.async_step_confirm()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if self.show_advanced_options:
            return await self.async_step_config()
        return await self.async_step_confirm()

    async def async_step_config(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the setup."""
        errors = {}
        data = {CONF_DISCOVERY_PREFIX: self._prefix}

        if user_input is not None:
            bad_prefix = False
            prefix = user_input[CONF_DISCOVERY_PREFIX]
            prefix = prefix.removesuffix("/#")
            try:
                valid_subscribe_topic(f"{prefix}/#")
            except vol.Invalid:
                errors["base"] = "invalid_discovery_topic"
                bad_prefix = True
            else:
                data[CONF_DISCOVERY_PREFIX] = prefix
            if not bad_prefix:
                return self.async_create_entry(title="Tasmota", data=data)

        fields = {}
        fields[vol.Optional(CONF_DISCOVERY_PREFIX, default=self._prefix)] = str

        return self.async_show_form(
            step_id="config", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the setup."""

        data = {CONF_DISCOVERY_PREFIX: self._prefix}

        if user_input is not None:
            return self.async_create_entry(title="Tasmota", data=data)

        return self.async_show_form(step_id="confirm")
