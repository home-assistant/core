"""Support for MQTT switches."""
import functools

import voluptuous as vol

from homeassistant.components import switch
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import (
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_VALUE_TEMPLATE,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from . import (
    CONF_COMMAND_TOPIC,
    CONF_QOS,
    CONF_RETAIN,
    CONF_STATE_TOPIC,
    DOMAIN,
    PLATFORMS,
    subscription,
)
from .. import mqtt
from .debug_info import log_messages
from .mixins import MQTT_ENTITY_COMMON_SCHEMA, MqttEntity, async_setup_entry_helper

DEFAULT_NAME = "MQTT Switch"
DEFAULT_PAYLOAD_ON = "ON"
DEFAULT_PAYLOAD_OFF = "OFF"
DEFAULT_OPTIMISTIC = False
CONF_STATE_ON = "state_on"
CONF_STATE_OFF = "state_off"

PLATFORM_SCHEMA = mqtt.MQTT_RW_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
        vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
        vol.Optional(CONF_STATE_OFF): cv.string,
        vol.Optional(CONF_STATE_ON): cv.string,
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)


async def async_setup_platform(
    hass: HomeAssistant, config: ConfigType, async_add_entities, discovery_info=None
):
    """Set up MQTT switch through configuration.yaml."""
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    await _async_setup_entity(hass, async_add_entities, config)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT switch dynamically through MQTT discovery."""
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, switch.DOMAIN, setup, PLATFORM_SCHEMA)


async def _async_setup_entity(
    hass, async_add_entities, config, config_entry=None, discovery_data=None
):
    """Set up the MQTT switch."""
    async_add_entities([MqttSwitch(hass, config, config_entry, discovery_data)])


class MqttSwitch(MqttEntity, SwitchEntity, RestoreEntity):
    """Representation of a switch that can be toggled using MQTT."""

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize the MQTT switch."""
        self._state = False

        self._state_on = None
        self._state_off = None
        self._optimistic = None

        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema():
        """Return the config schema."""
        return PLATFORM_SCHEMA

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""
        state_on = config.get(CONF_STATE_ON)
        self._state_on = state_on if state_on else config[CONF_PAYLOAD_ON]

        state_off = config.get(CONF_STATE_OFF)
        self._state_off = state_off if state_off else config[CONF_PAYLOAD_OFF]

        self._optimistic = config[CONF_OPTIMISTIC]

        template = self._config.get(CONF_VALUE_TEMPLATE)
        if template is not None:
            template.hass = self.hass

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""

        @callback
        @log_messages(self.hass, self.entity_id)
        def state_message_received(msg):
            """Handle new MQTT state messages."""
            payload = msg.payload
            template = self._config.get(CONF_VALUE_TEMPLATE)
            if template is not None:
                payload = template.async_render_with_possible_json_value(payload)
            if payload == self._state_on:
                self._state = True
            elif payload == self._state_off:
                self._state = False

            self.async_write_ha_state()

        if self._config.get(CONF_STATE_TOPIC) is None:
            # Force into optimistic mode.
            self._optimistic = True
        else:
            self._sub_state = await subscription.async_subscribe_topics(
                self.hass,
                self._sub_state,
                {
                    CONF_STATE_TOPIC: {
                        "topic": self._config.get(CONF_STATE_TOPIC),
                        "msg_callback": state_message_received,
                        "qos": self._config[CONF_QOS],
                    }
                },
            )

        if self._optimistic:
            last_state = await self.async_get_last_state()
            if last_state:
                self._state = last_state.state == STATE_ON

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._optimistic

    async def async_turn_on(self, **kwargs):
        """Turn the device on.

        This method is a coroutine.
        """
        mqtt.async_publish(
            self.hass,
            self._config[CONF_COMMAND_TOPIC],
            self._config[CONF_PAYLOAD_ON],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )
        if self._optimistic:
            # Optimistically assume that switch has changed state.
            self._state = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the device off.

        This method is a coroutine.
        """
        mqtt.async_publish(
            self.hass,
            self._config[CONF_COMMAND_TOPIC],
            self._config[CONF_PAYLOAD_OFF],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )
        if self._optimistic:
            # Optimistically assume that switch has changed state.
            self._state = False
            self.async_write_ha_state()
