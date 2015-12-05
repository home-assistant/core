"""
homeassistant.components.sensor.mqtt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allows to configure a MQTT sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mqtt/
"""
import logging
from homeassistant.helpers.entity import Entity
import homeassistant.components.mqtt as mqtt

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "MQTT Sensor"
DEFAULT_QOS = 0

DEPENDENCIES = ['mqtt']


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Add MQTT Sensor. """

    if config.get('state_topic') is None:
        _LOGGER.error("Missing required variable: state_topic")
        return False

    add_devices_callback([MqttSensor(
        hass,
        config.get('name', DEFAULT_NAME),
        config.get('state_topic'),
        config.get('qos', DEFAULT_QOS),
        config.get('unit_of_measurement'),
        config.get('state_format'))])


# pylint: disable=too-many-arguments, too-many-instance-attributes
class MqttSensor(Entity):
    """ Represents a sensor that can be updated using MQTT. """
    def __init__(self, hass, name, state_topic, qos, unit_of_measurement,
                 state_format):
        self._state = "-"
        self._hass = hass
        self._name = name
        self._state_topic = state_topic
        self._qos = qos
        self._unit_of_measurement = unit_of_measurement
        self._parse = mqtt.FmtParser(state_format)

        def message_received(topic, payload, qos):
            """ A new MQTT message has been received. """
            self._state = self._parse(payload)
            self.update_ha_state()

        mqtt.subscribe(hass, self._state_topic, message_received, self._qos)

    @property
    def should_poll(self):
        """ No polling needed """
        return False

    @property
    def name(self):
        """ The name of the sensor """
        return self._name

    @property
    def unit_of_measurement(self):
        """ Unit this state is expressed in. """
        return self._unit_of_measurement

    @property
    def state(self):
        """ Returns the state of the entity. """
        return self._state
