"""
This platform enables the possibility to control a MQTT alarm.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.mqtt/
"""
import logging

import voluptuous as vol

import homeassistant.components.alarm_control_panel as alarm
import homeassistant.components.mqtt as mqtt
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING, STATE_ALARM_TRIGGERED, STATE_UNKNOWN,
    CONF_NAME)
from homeassistant.components.mqtt import (
    CONF_STATE_TOPIC, CONF_COMMAND_TOPIC, CONF_QOS)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['mqtt']

CONF_PAYLOAD_DISARM = 'payload_disarm'
CONF_PAYLOAD_ARM_HOME = 'payload_arm_home'
CONF_PAYLOAD_ARM_AWAY = 'payload_arm_away'
CONF_CODE = 'code'

DEFAULT_NAME = "MQTT Alarm"
DEFAULT_DISARM = "DISARM"
DEFAULT_ARM_HOME = "ARM_HOME"
DEFAULT_ARM_AWAY = "ARM_AWAY"

PLATFORM_SCHEMA = mqtt.MQTT_BASE_PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Required(CONF_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_PAYLOAD_DISARM, default=DEFAULT_DISARM): cv.string,
    vol.Optional(CONF_PAYLOAD_ARM_HOME, default=DEFAULT_ARM_HOME): cv.string,
    vol.Optional(CONF_PAYLOAD_ARM_AWAY, default=DEFAULT_ARM_AWAY): cv.string,
    vol.Optional(CONF_CODE): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the MQTT platform."""
    add_devices([MqttAlarm(
        hass,
        config[CONF_NAME],
        config[CONF_STATE_TOPIC],
        config[CONF_COMMAND_TOPIC],
        config[CONF_QOS],
        config[CONF_PAYLOAD_DISARM],
        config[CONF_PAYLOAD_ARM_HOME],
        config[CONF_PAYLOAD_ARM_AWAY],
        config.get(CONF_CODE))])


# pylint: disable=too-many-arguments, too-many-instance-attributes
# pylint: disable=abstract-method
class MqttAlarm(alarm.AlarmControlPanel):
    """Represent a MQTT alarm status."""

    def __init__(self, hass, name, state_topic, command_topic, qos,
                 payload_disarm, payload_arm_home, payload_arm_away, code):
        """Initalize the MQTT alarm panel."""
        self._state = STATE_UNKNOWN
        self._hass = hass
        self._name = name
        self._state_topic = state_topic
        self._command_topic = command_topic
        self._qos = qos
        self._payload_disarm = payload_disarm
        self._payload_arm_home = payload_arm_home
        self._payload_arm_away = payload_arm_away
        self._code = code

        def message_received(topic, payload, qos):
            """A new MQTT message has been received."""
            if payload not in (STATE_ALARM_DISARMED, STATE_ALARM_ARMED_HOME,
                               STATE_ALARM_ARMED_AWAY, STATE_ALARM_PENDING,
                               STATE_ALARM_TRIGGERED):
                _LOGGER.warning('Received unexpected payload: %s', payload)
                return
            self._state = payload
            self.update_ha_state()

        mqtt.subscribe(hass, self._state_topic, message_received, self._qos)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def code_format(self):
        """One or more characters if code is defined."""
        return None if self._code is None else '.+'

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        if not self._validate_code(code, 'disarming'):
            return
        mqtt.publish(self.hass, self._command_topic,
                     self._payload_disarm, self._qos)

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        if not self._validate_code(code, 'arming home'):
            return
        mqtt.publish(self.hass, self._command_topic,
                     self._payload_arm_home, self._qos)

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        if not self._validate_code(code, 'arming away'):
            return
        mqtt.publish(self.hass, self._command_topic,
                     self._payload_arm_away, self._qos)

    def _validate_code(self, code, state):
        """Validate given code."""
        check = self._code is None or code == self._code
        if not check:
            _LOGGER.warning('Wrong code entered for %s', state)
        return check
