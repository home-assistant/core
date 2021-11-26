"""Support for MQTT buttons."""
from __future__ import annotations

import functools

import voluptuous as vol

from homeassistant.components import button
from homeassistant.components.button import ButtonEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType

from . import PLATFORMS
from .. import mqtt
from .const import CONF_COMMAND_TOPIC, CONF_QOS, CONF_RETAIN, DOMAIN
from .mixins import MQTT_ENTITY_COMMON_SCHEMA, MqttEntity, async_setup_entry_helper

CONF_PAYLOAD_PRESS = "payload_press"
DEFAULT_NAME = "MQTT Button"
DEFAULT_PAYLOAD_PRESS = "PRESS"

PLATFORM_SCHEMA = mqtt.MQTT_BASE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_COMMAND_TOPIC): mqtt.valid_publish_topic,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PAYLOAD_PRESS, default=DEFAULT_PAYLOAD_PRESS): cv.string,
        vol.Optional(CONF_RETAIN, default=mqtt.DEFAULT_RETAIN): cv.boolean,
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

DISCOVERY_SCHEMA = PLATFORM_SCHEMA.extend({}, extra=vol.REMOVE_EXTRA)


async def async_setup_platform(
    hass: HomeAssistant, config: ConfigType, async_add_entities, discovery_info=None
):
    """Set up MQTT button through configuration.yaml."""
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    await _async_setup_entity(hass, async_add_entities, config)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT button dynamically through MQTT discovery."""
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, button.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass, async_add_entities, config, config_entry=None, discovery_data=None
):
    """Set up the MQTT button."""
    async_add_entities([MqttButton(hass, config, config_entry, discovery_data)])


class MqttButton(MqttEntity, ButtonEntity):
    """Representation of a switch that can be toggled using MQTT."""

    _entity_id_format = button.ENTITY_ID_FORMAT

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize the MQTT button."""
        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema():
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""

    async def async_press(self, **kwargs):
        """Turn the device on.

        This method is a coroutine.
        """
        await mqtt.async_publish(
            self.hass,
            self._config[CONF_COMMAND_TOPIC],
            self._config[CONF_PAYLOAD_PRESS],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )
