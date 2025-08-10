"""Config flow for Qbus."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from qbusmqttapi.discovery import QbusMqttDevice
from qbusmqttapi.factory import QbusMqttMessageFactory, QbusMqttTopicFactory

from homeassistant.components.mqtt import client as mqtt
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ID
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from .const import CONF_SERIAL_NUMBER, DOMAIN
from .coordinator import QbusConfigCoordinator

_LOGGER = logging.getLogger(__name__)


class QbusFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle Qbus config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._message_factory = QbusMqttMessageFactory()
        self._topic_factory = QbusMqttTopicFactory()

        self._gateway_topic = self._topic_factory.get_gateway_state_topic()
        self._config_topic = self._topic_factory.get_config_topic()
        self._device_topic = self._topic_factory.get_device_state_topic("+")

        self._device: QbusMqttDevice | None = None

    async def async_step_mqtt(
        self, discovery_info: MqttServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by MQTT discovery."""
        _LOGGER.debug("Running mqtt discovery for topic %s", discovery_info.topic)

        # Abort if the payload is empty
        if not discovery_info.payload:
            _LOGGER.debug("Payload empty")
            return self.async_abort(reason="invalid_discovery_info")

        match discovery_info.subscribed_topic:
            case self._gateway_topic:
                return await self._async_handle_gateway_topic(discovery_info)

            case self._config_topic:
                return await self._async_handle_config_topic(discovery_info)

            case self._device_topic:
                return await self._async_handle_device_topic(discovery_info)

        return self.async_abort(reason="invalid_discovery_info")

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the setup."""
        if TYPE_CHECKING:
            assert self._device is not None

        if user_input is not None:
            return self.async_create_entry(
                title=f"Controller {self._device.serial_number}",
                data={
                    CONF_SERIAL_NUMBER: self._device.serial_number,
                    CONF_ID: self._device.id,
                },
            )

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                CONF_SERIAL_NUMBER: self._device.serial_number,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        return self.async_abort(reason="not_supported")

    async def _async_handle_gateway_topic(
        self, discovery_info: MqttServiceInfo
    ) -> ConfigFlowResult:
        _LOGGER.debug("Handling gateway state")
        gateway_state = self._message_factory.parse_gateway_state(
            discovery_info.payload
        )

        if gateway_state is not None and gateway_state.online is True:
            _LOGGER.debug("Requesting config")
            await mqtt.async_publish(
                self.hass, self._topic_factory.get_get_config_topic(), b""
            )

        # Abort to wait for config topic
        return self.async_abort(reason="discovery_in_progress")

    async def _async_handle_config_topic(
        self, discovery_info: MqttServiceInfo
    ) -> ConfigFlowResult:
        _LOGGER.debug("Handling config topic")
        qbus_config = self._message_factory.parse_discovery(discovery_info.payload)

        if qbus_config is not None:
            QbusConfigCoordinator.get_or_create(self.hass).store_config(qbus_config)

            _LOGGER.debug("Requesting device states")
            device_ids = [x.id for x in qbus_config.devices]
            request = self._message_factory.create_state_request(device_ids)
            await mqtt.async_publish(self.hass, request.topic, request.payload)

        # Abort to wait for device topic
        return self.async_abort(reason="discovery_in_progress")

    async def _async_handle_device_topic(
        self, discovery_info: MqttServiceInfo
    ) -> ConfigFlowResult:
        _LOGGER.debug("Discovering device")
        qbus_config = await QbusConfigCoordinator.get_or_create(
            self.hass
        ).async_get_or_request_config()

        if qbus_config is None:
            _LOGGER.error("Qbus config not ready")
            return self.async_abort(reason="invalid_discovery_info")

        device_id = discovery_info.topic.split("/")[2]
        self._device = qbus_config.get_device_by_id(device_id)

        if self._device is None:
            _LOGGER.warning("Device with id '%s' not found in config", device_id)
            return self.async_abort(reason="invalid_discovery_info")

        await self.async_set_unique_id(self._device.serial_number)

        # Do not use error message "already_configured" (which is the
        # default), as this will result in unsubscribing from the triggered
        # mqtt topic. The topic subscribed to has a wildcard to allow
        # discovery of multiple devices. Unsubscribing would result in
        # not discovering new or unconfigured devices.
        self._abort_if_unique_id_configured(error="device_already_configured")

        self.context.update(
            {
                "title_placeholders": {
                    CONF_SERIAL_NUMBER: self._device.serial_number,
                }
            }
        )

        return await self.async_step_discovery_confirm()
