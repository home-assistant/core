"""Config flow Airzone MQTT integration."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from airzone_mqtt.const import TZ_UTC
from airzone_mqtt.exceptions import AirzoneMqttError
from airzone_mqtt.mqttapi import AirzoneMqttApi
import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.mqtt import PublishPayloadType, ReceiveMessage
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import callback

from .const import CONF_MQTT_TOPIC, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MQTT_TOPIC): str,
    }
)


class AirzoneConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for an Airzone MQTT device."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        async def mqtt_publish(
            topic: str,
            payload: PublishPayloadType,
            qos: int = 0,
            retain: bool = False,
        ) -> None:
            """Publish MQTT payload."""
            _LOGGER.debug("config_flow: mqtt_publish: topic=%s", topic)
            await mqtt.async_publish(
                hass=self.hass,
                topic=topic,
                payload=payload,
                qos=qos,
                retain=retain,
            )

        errors = {}

        if not await mqtt.async_wait_for_mqtt_client(self.hass):
            errors["base"] = "mqtt_unavailable"
        elif user_input is not None:
            self._async_abort_entries_match(user_input)

            airzone = AirzoneMqttApi(user_input[CONF_MQTT_TOPIC])
            airzone.mqtt_publish = mqtt_publish

            @callback
            def mqtt_callback(msg: ReceiveMessage) -> None:
                """Pass MQTT payload to Airzone library."""
                _LOGGER.debug("config_flow: mqtt_callback: topic=%s", msg.topic)
                airzone.msg_callback(
                    topic_str=msg.topic,
                    payload=str(msg.payload),
                    dt=datetime.fromtimestamp(msg.timestamp, tz=TZ_UTC),
                )

            mqtt_unsubscribe = await mqtt.async_subscribe(
                self.hass,
                f"{user_input[CONF_MQTT_TOPIC]}/v1/#",
                mqtt_callback,
            )

            try:
                await airzone.update()
            except AirzoneMqttError:
                errors["base"] = "cannot_connect"
            finally:
                mqtt_unsubscribe()

            if len(errors) == 0:
                title = f"Airzone MQTT {user_input[CONF_MQTT_TOPIC]}"
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=CONFIG_SCHEMA,
            errors=errors,
        )
