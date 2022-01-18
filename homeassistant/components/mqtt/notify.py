"""Support for MQTT nonify."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import notify
from homeassistant.const import CONF_NAME, CONF_SERVICE, CONF_SERVICE_DATA, CONF_TARGET
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .. import mqtt
from .const import CONF_ENCODING, CONF_QOS, CONF_RETAIN, DEFAULT_RETAIN, DOMAIN
from .siren import (
    CONF_MESSAGE_COMMAND_TEMPLATE,
    CONF_MESSAGE_COMMAND_TOPIC,
    CONF_SIREN_ENTITY,
    CONF_TITLE,
    MQTT_NOTIFY_CONFIG,
    MqttSiren,
)


def valid_siren_entity(value: Any) -> MqttSiren:
    """Validate if the value passed is a valid MqttSiren object."""
    if not isinstance(value, MqttSiren):
        raise vol.Invalid(f"Object {value} is not a valid MqttSiren entity")
    return value


SCHEMA_BASE = vol.Schema(
    {
        vol.Optional(CONF_SIREN_ENTITY): valid_siren_entity,
        vol.Optional(CONF_TARGET): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_MESSAGE_COMMAND_TOPIC): mqtt.valid_publish_topic,
        vol.Optional(CONF_MESSAGE_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_TITLE, default=notify.ATTR_TITLE_DEFAULT): cv.string,
        vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
    }
).extend(mqtt.SCHEMA_BASE)


async def async_get_service(
    hass: HomeAssistant,
    legacy_config: ConfigType,
    discovery_info: DiscoveryInfoType,
) -> MqttNotificationService | None:
    """Prepare the MQTT notification service."""
    config = SCHEMA_BASE(discovery_info)
    hass.data.setdefault(
        MQTT_NOTIFY_CONFIG, {CONF_SERVICE: None, CONF_SERVICE_DATA: {}}
    )
    target = config[CONF_MESSAGE_COMMAND_TOPIC]
    if hass.data[MQTT_NOTIFY_CONFIG][CONF_SERVICE_DATA].get(
        config[CONF_MESSAGE_COMMAND_TOPIC]
    ):
        raise ValueError(f"A notify service for target {target} is already setup.")
    hass.data[MQTT_NOTIFY_CONFIG][CONF_SERVICE_DATA][target] = {
        CONF_ENCODING: config[CONF_ENCODING],
        CONF_TARGET: target,
        CONF_NAME: config.get(CONF_TARGET) or config.get(CONF_NAME) or target,
        CONF_MESSAGE_COMMAND_TOPIC: config[CONF_MESSAGE_COMMAND_TOPIC],
        CONF_MESSAGE_COMMAND_TEMPLATE: mqtt.MqttCommandTemplate(
            config.get(CONF_MESSAGE_COMMAND_TEMPLATE),
            hass=hass,
            entity=config.get(CONF_SIREN_ENTITY),
        ).async_render,
        CONF_QOS: config[CONF_QOS],
        CONF_RETAIN: config[CONF_RETAIN],
        CONF_TITLE: config[CONF_TITLE],
    }
    discovery_info[CONF_NAME] = DOMAIN
    return hass.data[MQTT_NOTIFY_CONFIG][CONF_SERVICE] or MqttNotificationService(hass)


class MqttNotificationService(notify.BaseNotificationService):
    """Implement the notification service for E-mail messages."""

    def __init__(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the service."""
        self.hass = hass
        self.hass.data.setdefault(
            MQTT_NOTIFY_CONFIG, {CONF_SERVICE: None, CONF_SERVICE_DATA: {}}
        )
        hass.data[MQTT_NOTIFY_CONFIG][CONF_SERVICE] = self
        self._config = hass.data[MQTT_NOTIFY_CONFIG][CONF_SERVICE_DATA]

    @property
    def targets(self) -> dict[str, str]:
        """Return a dictionary of registered targets."""
        return {entry[CONF_NAME]: id for id, entry in self._config.items()}

    async def async_send_message(self, message: str = "", **kwargs):
        """Build and send a MQTT message to a target."""
        for target in kwargs.get(notify.ATTR_TARGET, []):
            if (target_config := self._config.get(target)) is None:
                continue
            variables = {
                "data": kwargs.get(notify.ATTR_DATA),
                "message": message,
                "target_name": target_config[CONF_NAME],
                "target_id": target,
                "title": kwargs.get(notify.ATTR_TITLE, target_config[CONF_TITLE]),
            }
            payload = target_config[CONF_MESSAGE_COMMAND_TEMPLATE](
                message, variables=variables
            )
            await mqtt.async_publish(
                self.hass,
                target_config[CONF_MESSAGE_COMMAND_TOPIC],
                payload,
                target_config[CONF_QOS],
                target_config[CONF_RETAIN],
                target_config[CONF_ENCODING],
            )
