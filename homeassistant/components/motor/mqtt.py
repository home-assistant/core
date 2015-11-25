"""
homeassistant.components.motor.mqtt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allows to configure a MQTT motor.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/motor.mqtt/
"""
import logging
import homeassistant.components.mqtt as mqtt
from homeassistant.components.motor import MotorDevice
_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['mqtt']

DEFAULT_NAME = "MQTT Motor"
DEFAULT_QOS = 0
DEFAULT_PAYLOAD_OPEN = "OPEN"
DEFAULT_PAYLOAD_CLOSE = "CLOSE"
DEFAULT_PAYLOAD_STOP = "STOP"

ATTR_CURRENT_POSITION = 'current_position'


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Add MQTT Motor """

    if config.get('command_topic') is None:
        _LOGGER.error("Missing required variable: command_topic")
        return False

    add_devices_callback([MqttMotor(
        hass,
        config.get('name', DEFAULT_NAME),
        config.get('state_topic'),
        config.get('command_topic'),
        config.get('qos', DEFAULT_QOS),
        config.get('payload_open', DEFAULT_PAYLOAD_OPEN),
        config.get('payload_close', DEFAULT_PAYLOAD_CLOSE),
        config.get('payload_stop', DEFAULT_PAYLOAD_STOP),
        config.get('state_format'))])


# pylint: disable=too-many-arguments, too-many-instance-attributes
class MqttMotor(MotorDevice):
    """ Represents a motor that can be controlled using MQTT """
    def __init__(self, hass, name, state_topic, command_topic, qos,
                 payload_open, payload_close, payload_stop, state_format):
        self._state = None
        self._hass = hass
        self._name = name
        self._state_topic = state_topic
        self._command_topic = command_topic
        self._qos = qos
        self._payload_open = payload_open
        self._payload_close = payload_close
        self._payload_stop = payload_stop
        self._parse = mqtt.FmtParser(state_format)

        if self._state_topic is None:
            return

        def message_received(topic, payload, qos):
            """ A new MQTT message has been received. """
            value = self._parse(payload)
            if value.isnumeric() and 0 <= int(value) <= 100:
                self._state = int(value)
                self.update_ha_state()
            else:
                _LOGGER.warning(
                    "Payload is expected to be an integer between 0 and 100")

        mqtt.subscribe(hass, self._state_topic, message_received, self._qos)

    @property
    def should_poll(self):
        """ No polling needed """
        return False

    @property
    def name(self):
        """ The name of the motor """
        return self._name

    @property
    def current_position(self):
        """ Return current position of motor.
        None is unknown, 0 is closed, 100 is fully open. """
        return self._state

    @property
    def is_open(self):
        """ True if device is open. """
        return self._state > 0

    def open(self, **kwargs):
        """ Close the device. """
        mqtt.publish(self.hass, self._command_topic, self._payload_open,
                     self._qos)

    def close(self, **kwargs):
        """ Open the device. """
        mqtt.publish(self.hass, self._command_topic, self._payload_close,
                     self._qos)

    def stop(self, **kwargs):
        """ Stop the device. """
        mqtt.publish(self.hass, self._command_topic, self._payload_stop,
                     self._qos)

    @property
    def state_attributes(self):
        """ Return the state attributes. """
        state_attr = {}
        if self._state is not None:
            state_attr[ATTR_CURRENT_POSITION] = self._state
        return state_attr
