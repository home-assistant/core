"""Support for MQTT nonify."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import notify
from homeassistant.const import CONF_NAME, CONF_SERVICE, CONF_SERVICE_DATA, CONF_TARGET
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify

from .. import mqtt
from .const import CONF_ENCODING, CONF_QOS, CONF_RETAIN, DEFAULT_RETAIN, DOMAIN
from .siren import (
    CONF_MESSAGE_COMMAND_TEMPLATE,
    CONF_MESSAGE_COMMAND_TOPIC,
    CONF_TITLE,
    MQTT_NOTIFY_CONFIG,
    SIREN_ENTITY,
    MqttSiren,
)


def valid_siren_entity(value: Any) -> MqttSiren:
    """Validate if the value passed is a valid MqttSiren object."""
    if not isinstance(value, MqttSiren):
        raise vol.Invalid(f"Object {value} is not a valid MqttSiren entity")
    return value


SCHEMA_BASE = vol.Schema(
    {
        vol.Optional(SIREN_ENTITY): valid_siren_entity,
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
    if (
        SIREN_ENTITY in config
        and config[SIREN_ENTITY].target
        in hass.data[MQTT_NOTIFY_CONFIG][CONF_SERVICE_DATA]
    ):
        # Remove the old target and trigger a service reload
        del hass.data[MQTT_NOTIFY_CONFIG][CONF_SERVICE_DATA][
            config[SIREN_ENTITY].target
        ]
        await hass.data[MQTT_NOTIFY_CONFIG][CONF_SERVICE].async_register_services()

    target = config[CONF_MESSAGE_COMMAND_TOPIC]
    hass.data[MQTT_NOTIFY_CONFIG][CONF_SERVICE_DATA][target] = {
        CONF_ENCODING: config[CONF_ENCODING],
        CONF_TARGET: target,
        CONF_NAME: config.get(CONF_TARGET) or config.get(CONF_NAME) or target,
        CONF_MESSAGE_COMMAND_TOPIC: config[CONF_MESSAGE_COMMAND_TOPIC],
        CONF_MESSAGE_COMMAND_TEMPLATE: mqtt.MqttCommandTemplate(
            config.get(CONF_MESSAGE_COMMAND_TEMPLATE),
            hass=hass,
            entity=config.get(SIREN_ENTITY),
        ).async_render,
        CONF_QOS: config[CONF_QOS],
        CONF_RETAIN: config[CONF_RETAIN],
        CONF_TITLE: config[CONF_TITLE],
    }
    if SIREN_ENTITY in config:
        config[SIREN_ENTITY].target = target

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
        target = kwargs.get(notify.ATTR_TARGET, [])
        for key, target_config in self._config.items():
            if (
                key not in target
                and target_config[CONF_NAME] not in target
                and slugify(target_config[CONF_NAME]) not in target
            ):
                continue
            variables = {
                "data": kwargs.get(notify.ATTR_DATA),
                "message": message,
                "target_name": target_config[CONF_NAME],
                "target_id": key,
                "title": kwargs.get(notify.ATTR_TITLE, target_config[CONF_TITLE]),
            }
            if kwargs.get(notify.ATTR_DATA):
                variables.update(kwargs[notify.ATTR_DATA])
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
