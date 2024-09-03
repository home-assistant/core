"""Config flow for Qbus."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from qbusmqttapi.discovery import QbusDiscovery
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from .const import (
    CONF_CONFIG_TOPIC,
    CONF_SERIAL,
    CONF_STATE_MESSAGE,
    CONFIG_TOPIC,
    DEVICE_CONFIG_TOPIC,
    DOMAIN,
    NAME,
)


class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Qbus config flow."""

    VERSION = 1

    _qbus_config: QbusDiscovery | None = None

    async def async_step_mqtt(
        self, discovery_info: MqttServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by MQTT discovery."""

        # Abort if the topic does not match our discovery topic or the payload is empty.
        if (
            discovery_info.subscribed_topic != CONFIG_TOPIC
            or not discovery_info.payload
        ):
            return self.async_abort(reason="invalid_discovery_info")

        self._qbus_config = QbusDiscovery(DOMAIN)

        if not (
            await self._qbus_config.parse_config(
                discovery_info.topic, discovery_info.payload
            )
        ):
            return self.async_abort(reason="invalid_discovery_info")

        existing_entry = await self.async_set_unique_id(DOMAIN)

        if existing_entry is not None:
            return self.async_abort(reason="invalid_discovery_info")

        self.context.update({"title_placeholders": {"name": DOMAIN}})

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the setup."""
        if TYPE_CHECKING:
            assert self._qbus_config is not None
        if user_input is not None:
            await self.async_set_unique_id(user_input.get("id"))
            qid = user_input.get("id")
            device = self._qbus_config.set_device(qid)

            device_data = {
                NAME: device.name,
                CONF_SERIAL: device.id,
                CONF_STATE_MESSAGE: device.state_message,
                DEVICE_CONFIG_TOPIC: self._qbus_config.config_topic,
            }

            # Create the device
            return self.async_create_entry(title=device.serial_number, data=device_data)

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "device_name": self.unique_id,
            },
            data_schema=vol.Schema(
                {
                    vol.Required("id"): vol.In(
                        {
                            **{
                                device.id: device.serial_number
                                for device in self._qbus_config.devices
                            }
                        }
                    ),
                }
            ),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if self._qbus_config is None:
            await mqtt.async_publish(self.hass, CONF_CONFIG_TOPIC, b"")
        return self.async_abort(reason="not_supported")
