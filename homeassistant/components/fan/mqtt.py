"""
Support for MQTT fans.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/fan.mqtt/
"""
import logging
from functools import partial

import voluptuous as vol

import homeassistant.components.mqtt as mqtt
from homeassistant.const import CONF_NAME, CONF_OPTIMISTIC
from homeassistant.components.mqtt import (
    CONF_STATE_TOPIC, CONF_COMMAND_TOPIC, CONF_QOS, CONF_RETAIN)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.template import render_with_possible_json_value
from homeassistant.components.fan import (SPEED_LOW, SPEED_MED, SPEED_HIGH,
                                          FanEntity, SUPPORT_SET_SPEED,
                                          SUPPORT_OSCILLATE, SPEED_OFF)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['mqtt']

CONF_STATE_VALUE_TEMPLATE = 'state_value_template'
CONF_SPEED_STATE_TOPIC = 'speed_state_topic'
CONF_SPEED_COMMAND_TOPIC = 'speed_command_topic'
CONF_SPEED_VALUE_TEMPLATE = 'speed_value_template'
CONF_OSCILLATION_STATE_TOPIC = 'oscillation_state_topic'
CONF_OSCILLATION_COMMAND_TOPIC = 'oscillation_command_topic'
CONF_OSCILLATION_VALUE_TEMPLATE = 'oscillation_value_template'
CONF_PAYLOAD_ON = 'payload_on'
CONF_PAYLOAD_OFF = 'payload_off'
CONF_PAYLOAD_OSCILLATION_ON = 'payload_oscillation_on'
CONF_PAYLOAD_OSCILLATION_OFF = 'payload_oscillation_off'
CONF_PAYLOAD_LOW_SPEED = 'payload_low_speed'
CONF_PAYLOAD_MEDIUM_SPEED = 'payload_medium_speed'
CONF_PAYLOAD_HIGH_SPEED = 'payload_high_speed'
CONF_SPEED_LIST = 'speeds'

DEFAULT_NAME = 'MQTT Fan'
DEFAULT_PAYLOAD_ON = 'ON'
DEFAULT_PAYLOAD_OFF = 'OFF'
DEFAULT_OPTIMISTIC = False

PLATFORM_SCHEMA = mqtt.MQTT_RW_PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_STATE_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_SPEED_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_SPEED_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_SPEED_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_OSCILLATION_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_OSCILLATION_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_OSCILLATION_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
    vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
    vol.Optional(CONF_PAYLOAD_OSCILLATION_ON,
                 default=DEFAULT_PAYLOAD_ON): cv.string,
    vol.Optional(CONF_PAYLOAD_OSCILLATION_OFF,
                 default=DEFAULT_PAYLOAD_OFF): cv.string,
    vol.Optional(CONF_PAYLOAD_LOW_SPEED, default=SPEED_LOW): cv.string,
    vol.Optional(CONF_PAYLOAD_MEDIUM_SPEED, default=SPEED_MED): cv.string,
    vol.Optional(CONF_PAYLOAD_HIGH_SPEED, default=SPEED_HIGH): cv.string,
    vol.Optional(CONF_SPEED_LIST,
                 default=[SPEED_OFF, SPEED_LOW,
                          SPEED_MED, SPEED_HIGH]): cv.ensure_list,
    vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup MQTT fan platform."""
    add_devices_callback([MqttFan(
        hass,
        config[CONF_NAME],
        {
            key: config.get(key) for key in (
                CONF_STATE_TOPIC,
                CONF_COMMAND_TOPIC,
                CONF_SPEED_STATE_TOPIC,
                CONF_SPEED_COMMAND_TOPIC,
                CONF_OSCILLATION_STATE_TOPIC,
                CONF_OSCILLATION_COMMAND_TOPIC,
            )
        },
        {
            'state': config.get(CONF_STATE_VALUE_TEMPLATE),
            'speed': config.get(CONF_SPEED_VALUE_TEMPLATE),
            'oscillation': config.get(CONF_OSCILLATION_VALUE_TEMPLATE)
        },
        config[CONF_QOS],
        config[CONF_RETAIN],
        {
            'on': config[CONF_PAYLOAD_ON],
            'off': config[CONF_PAYLOAD_OFF],
            'oscillate_on': config[CONF_PAYLOAD_OSCILLATION_ON],
            'oscillate_off': config[CONF_PAYLOAD_OSCILLATION_OFF],
            'low': config[CONF_PAYLOAD_LOW_SPEED],
            'medium': config[CONF_PAYLOAD_MEDIUM_SPEED],
            'high': config[CONF_PAYLOAD_HIGH_SPEED],
        },
        config[CONF_SPEED_LIST],
        config[CONF_OPTIMISTIC],
    )])


class MqttFan(FanEntity):
    """A MQTT fan component."""

    def __init__(self, hass, name, topic, templates, qos, retain, payload,
                 speed_list, optimistic):
        """Initialize MQTT fan."""
        self._hass = hass
        self._name = name
        self._topic = topic
        self._qos = qos
        self._retain = retain
        self._payload = payload
        self._speed_list = speed_list
        self._optimistic = optimistic or topic["state_topic"] is None
        self._optimistic_oscillation = (optimistic or
                                        topic["oscillation_state_topic"]
                                        is None)
        self._optimistic_speed = (optimistic or
                                  topic["speed_state_topic"] is None)
        self._state = False
        self._supported_features = 0
        self._supported_features |= (
            topic['oscillation_state_topic'] is not None and SUPPORT_OSCILLATE)
        self._supported_features |= (
            topic['speed_state_topic'] is not None and SUPPORT_SET_SPEED)

        templates = {key: ((lambda value: value) if tpl is None else
                           partial(render_with_possible_json_value, hass, tpl))
                     for key, tpl in templates.items()}

        def state_received(topic, payload, qos):
            """A new MQTT message has been received."""
            payload = templates['state'](payload)
            if payload == self._payload["on"]:
                self._state = True
            elif payload == self._payload["off"]:
                self._state = False

            self.update_ha_state()

        if self._topic["state_topic"] is not None:
            mqtt.subscribe(self._hass, self._topic["state_topic"],
                           state_received, self._qos)

        def speed_received(topic, payload, qos):
            """A new MQTT message for the speed has been received."""
            payload = templates['speed'](payload)
            if payload == self._payload["low"]:
                self._speed = SPEED_LOW
            elif payload == self._payload["medium"]:
                self._speed = SPEED_MED
            elif payload == self._payload["high"]:
                self._speed = SPEED_HIGH
            self.update_ha_state()

        if self._topic["speed_state_topic"] is not None:
            mqtt.subscribe(self._hass, self._topic["speed_state_topic"],
                           speed_received, self._qos)
            self._speed = SPEED_OFF
        elif self._topic["speed_command_topic"] is not None:
            self._speed = SPEED_OFF
        else:
            self._speed = SPEED_OFF

        def oscillation_received(topic, payload, qos):
            """A new MQTT message has been received."""
            payload = templates['oscillation'](payload)
            if payload == self._payload["oscillate_on"]:
                self._oscillation = True
            elif payload == self._payload["oscillate_off"]:
                self._oscillation = False
            self.update_ha_state()

        if self._topic["oscillation_state_topic"] is not None:
            mqtt.subscribe(self._hass, self._topic["oscillation_state_topic"],
                           oscillation_received, self._qos)
            self._oscillation = False
        if self._topic["oscillation_command_topic"] is not None:
            self._oscillation = False
        else:
            self._oscillation = False

    @property
    def should_poll(self):
        """No polling needed for a MQTT fan."""
        return False

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._optimistic

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def name(self) -> str:
        """Get entity name."""
        return self._name

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return self._speed_list

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    @property
    def speed(self):
        """Return the current speed."""
        return self._speed

    @property
    def oscillating(self):
        """Return the current speed."""
        return self._oscillation

    def turn_on(self, speed: str=SPEED_MED) -> None:
        """Turn on the entity."""
        mqtt.publish(self._hass, self._topic["command_topic"],
                     self._payload["on"], self._qos, self._retain)
        self.set_speed(speed)

    def turn_off(self) -> None:
        """Turn off the entity."""
        mqtt.publish(self._hass, self._topic["command_topic"],
                     self._payload["off"], self._qos, self._retain)

    def set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        if self._topic["speed_command_topic"] is not None:
            mqtt_payload = SPEED_OFF
            if speed == SPEED_LOW:
                mqtt_payload = self._payload["low"]
            elif speed == SPEED_MED:
                mqtt_payload = self._payload["medium"]
            elif speed == SPEED_HIGH:
                mqtt_payload = self._payload["high"]
            else:
                mqtt_payload = speed
            self._speed = speed
            mqtt.publish(self._hass, self._topic["speed_command_topic"],
                         mqtt_payload, self._qos, self._retain)
            self.update_ha_state()

    def oscillate(self, oscillating: bool) -> None:
        """Set oscillation."""
        if self._topic["speed_command_topic"] is not None:
            self._oscillation = oscillating
            mqtt.publish(self._hass, self._topic["oscillation_command_topic"],
                         self._oscillation, self._qos, self._retain)
            self.update_ha_state()
