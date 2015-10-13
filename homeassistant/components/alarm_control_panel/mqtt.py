"""
homeassistant.components.alarm_control_panel.mqtt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This platform enables the possibility to control a MQTT alarm.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.mqtt.html
"""
import logging
import homeassistant.components.mqtt as mqtt
import homeassistant.components.alarm_control_panel as alarm

from homeassistant.const import (STATE_UNKNOWN)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "MQTT Alarm"
DEFAULT_QOS = 0
DEFAULT_PAYLOAD_DISARM = "DISARM"
DEFAULT_PAYLOAD_ARM_HOME = "ARM_HOME"
DEFAULT_PAYLOAD_ARM_AWAY = "ARM_AWAY"

DEPENDENCIES = ['mqtt']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the MQTT platform. """

    if config.get('state_topic') is None:
        _LOGGER.error("Missing required variable: state_topic")
        return False

    if config.get('command_topic') is None:
        _LOGGER.error("Missing required variable: command_topic")
        return False

    add_devices([MqttAlarm(
        hass,
        config.get('name', DEFAULT_NAME),
        config.get('state_topic'),
        config.get('command_topic'),
        config.get('qos', DEFAULT_QOS),
        config.get('payload_disarm', DEFAULT_PAYLOAD_DISARM),
        config.get('payload_arm_home', DEFAULT_PAYLOAD_ARM_HOME),
        config.get('payload_arm_away', DEFAULT_PAYLOAD_ARM_AWAY),
        config.get('code'))])


# pylint: disable=too-many-arguments, too-many-instance-attributes
# pylint: disable=abstract-method
class MqttAlarm(alarm.AlarmControlPanel):
    """ represents a MQTT alarm status within home assistant. """

    def __init__(self, hass, name, state_topic, command_topic, qos,
                 payload_disarm, payload_arm_home, payload_arm_away, code):
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
            """ A new MQTT message has been received. """
            self._state = payload
            self.update_ha_state()

        mqtt.subscribe(hass, self._state_topic, message_received, self._qos)

    @property
    def should_poll(self):
        """ No polling needed """
        return False

    @property
    def name(self):
        """ Returns the name of the device. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    @property
    def code_format(self):
        """ One or more characters if code is defined """
        return None if self._code is None else '.+'

    def alarm_disarm(self, code=None):
        """ Send disarm command. """
        if code == str(self._code) or self.code_format is None:
            mqtt.publish(self.hass, self._command_topic,
                         self._payload_disarm, self._qos)
        else:
            _LOGGER.warning("Wrong code entered while disarming!")

    def alarm_arm_home(self, code=None):
        """ Send arm home command. """
        if code == str(self._code) or self.code_format is None:
            mqtt.publish(self.hass, self._command_topic,
                         self._payload_arm_home, self._qos)
        else:
            _LOGGER.warning("Wrong code entered while arming home!")

    def alarm_arm_away(self, code=None):
        """ Send arm away command. """
        if code == str(self._code) or self.code_format is None:
            mqtt.publish(self.hass, self._command_topic,
                         self._payload_arm_away, self._qos)
        else:
            _LOGGER.warning("Wrong code entered while arming away!")
