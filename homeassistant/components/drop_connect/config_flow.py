"""Config flow for drop_connect integration."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from dropmqttapi.discovery import DropDiscovery

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from .const import (
    CONF_COMMAND_TOPIC,
    CONF_DATA_TOPIC,
    CONF_DEVICE_DESC,
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_DEVICE_OWNER_ID,
    CONF_DEVICE_TYPE,
    CONF_HUB_ID,
    DISCOVERY_TOPIC,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle DROP config flow."""

    VERSION = 1

    _drop_discovery: DropDiscovery | None = None

    async def async_step_mqtt(self, discovery_info: MqttServiceInfo) -> FlowResult:
        """Handle a flow initialized by MQTT discovery."""

        # Abort if the topic does not match our discovery topic or the payload is empty.
        if (
            discovery_info.subscribed_topic != DISCOVERY_TOPIC
            or not discovery_info.payload
        ):
            return self.async_abort(reason="invalid_discovery_info")

        self._drop_discovery = DropDiscovery(DOMAIN)
        if not (
            await self._drop_discovery.parse_discovery(
                discovery_info.topic, discovery_info.payload
            )
        ):
            return self.async_abort(reason="invalid_discovery_info")
        existing_entry = await self.async_set_unique_id(
            f"{self._drop_discovery.hub_id}_{self._drop_discovery.device_id}"
        )
        if existing_entry is not None:
            # Note: returning "invalid_discovery_info" here instead of "already_configured"
            # allows discovery of additional device types.
            return self.async_abort(reason="invalid_discovery_info")

        self.context.update({"title_placeholders": {"name": self._drop_discovery.name}})

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm the setup."""
        if TYPE_CHECKING:
            assert self._drop_discovery is not None
        if user_input is not None:
            device_data = {
                CONF_COMMAND_TOPIC: self._drop_discovery.command_topic,
                CONF_DATA_TOPIC: self._drop_discovery.data_topic,
                CONF_DEVICE_DESC: self._drop_discovery.device_desc,
                CONF_DEVICE_ID: self._drop_discovery.device_id,
                CONF_DEVICE_NAME: self._drop_discovery.name,
                CONF_DEVICE_TYPE: self._drop_discovery.device_type,
                CONF_HUB_ID: self._drop_discovery.hub_id,
                CONF_DEVICE_OWNER_ID: self._drop_discovery.owner_id,
            }
            return self.async_create_entry(
                title=self._drop_discovery.name, data=device_data
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "device_name": self._drop_discovery.name,
                "device_type": self._drop_discovery.device_desc,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        return self.async_abort(reason="not_supported")
