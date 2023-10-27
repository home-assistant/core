"""Config flow to configure OpenEVSE."""
from __future__ import annotations

from collections.abc import Awaitable
import json
import logging
from typing import Any

from homeassistant.components import onboarding
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.config_entry_flow import DiscoveryFlowHandler
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from .const import CONF_BASE_TOPIC, CONF_CONFIG_URL, CONF_UNIQUE_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def _async_has_devices(_: HomeAssistant) -> bool:
    """MQTT is set as dependency, so that should be sufficient."""
    return True


class OpenEvseFlowHandler(DiscoveryFlowHandler[Awaitable[bool]], domain=DOMAIN):
    """Handle OpenEVSE config flow. The MQTT step is inherited from the parent class."""

    VERSION = 1

    def __init__(self) -> None:
        """Set up the config flow."""
        super().__init__(DOMAIN, "OpenEVSE", _async_has_devices)

    async def async_step_mqtt(self, discovery_info: MqttServiceInfo) -> FlowResult:
        """Handle a flow initialized by MQTT discovery."""
        device_info: dict[str, Any] = json.loads(discovery_info.payload)
        _LOGGER.debug("async_step_mqtt got discovery_info: %s", discovery_info)
        _LOGGER.debug("async_step_mqtt got device info: %s", device_info)

        device_id: str = device_info["id"]
        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured()

        # Remember discovered device details for later step
        self.context[CONF_BASE_TOPIC] = device_info["mqtt"]
        self.context[CONF_CONFIG_URL] = device_info["http"]

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm setup."""
        # if user_input is None:
        #     # TODO: Is this confirm step even necessary?
        #     return self.async_show_form(step_id="confirm")

        if user_input is None and onboarding.async_is_onboarded(self.hass):
            self._set_confirm_only()
            return self.async_show_form(step_id="confirm")

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        # Build ConfigEntry using data we discovered earlier
        return self.async_create_entry(
            title=self._title,
            data={
                CONF_UNIQUE_ID: self.context[CONF_UNIQUE_ID],
                CONF_BASE_TOPIC: self.context[CONF_BASE_TOPIC],
                CONF_CONFIG_URL: self.context[CONF_CONFIG_URL],
            },
        )
