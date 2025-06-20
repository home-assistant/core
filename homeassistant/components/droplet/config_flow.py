"""Config flow for Droplet integration."""

from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from .const import (
    CONF_DATA_TOPIC,
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_HEALTH_TOPIC,
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_SERIAL,
    CONF_SW,
    DOMAIN,
)
from .dropletmqtt import DropletDiscovery

_LOGGER = logging.getLogger(__name__)


class FlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle Droplet config flow."""

    VERSION = 1

    _droplet_discovery: DropletDiscovery | None = None

    async def async_step_mqtt(
        self, discovery_info: MqttServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by MQTT discovery."""

        _LOGGER.info(discovery_info)

        try:
            payload = json.loads(discovery_info.payload)
        except json.JSONDecodeError:
            return self.async_abort(reason="invalid_discovery_info")

        self._droplet_discovery = DropletDiscovery(discovery_info.topic, payload)

        if self._droplet_discovery is None or not self._droplet_discovery.is_valid():
            return self.async_abort(reason="invalid_discovery_info")

        await self.async_set_unique_id(f"{self._droplet_discovery.device_id}")
        self._abort_if_unique_id_configured()

        self.context.update(
            {"title_placeholders": {"name": self._droplet_discovery.name}}
        )

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the setup."""
        if self._droplet_discovery is None:
            return self.async_abort(reason="device_not_found")
        if user_input is not None:
            device_data = {
                CONF_DATA_TOPIC: self._droplet_discovery.data_topic,
                CONF_HEALTH_TOPIC: self._droplet_discovery.health_topic,
                CONF_DEVICE_ID: self._droplet_discovery.device_id,
                CONF_DEVICE_NAME: self._droplet_discovery.name,
                CONF_MANUFACTURER: self._droplet_discovery.manufacturer,
                CONF_MODEL: self._droplet_discovery.model,
                CONF_SW: self._droplet_discovery.fw_version,
                CONF_SERIAL: self._droplet_discovery.serial_number,
            }
            return self.async_create_entry(
                title=self._droplet_discovery.name, data=device_data
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "device_name": self._droplet_discovery.name,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        return self.async_abort(reason="not_supported")
