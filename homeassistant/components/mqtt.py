"""
homeassistant.components.mqtt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
MQTT component, using paho-mqtt. This component needs a MQTT broker like
Mosquitto or Mosca. The Eclipse Foundation is running a public MQTT server
at iot.eclipse.org. If you prefer to use that one, keep in mind to adjust
the topic/client ID and that your messages are public.

Configuration:

To use MQTT you will need to add something like the following to your
config/configuration.yaml.

mqtt:
  broker: 127.0.0.1
  port: 1883
  topic: home-assistant
  keepalive: 60
  qos: 0

Variables:

broker
*Required
This is the IP address of your MQTT broker, e.g. 192.168.1.32.

port
*Optional
The network port to connect to. Default is 1883.

topic
*Optional
The MQTT topic to subscribe to. Default is home-assistant.

keepalive
*Optional
The keep alive in seconds for this client, e.g. 60.

qos
*Optional
Quality of service level to use for the subscription.
0, 1, or 2, defaults to 0.
"""
import logging
import socket

import homeassistant.util as util
from homeassistant.helpers import validate_config
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "mqtt"

MQTT_CLIENT = None

DEFAULT_TOPIC = 'home-assistant'
DEFAULT_PORT = 1883
DEFAULT_KEEPALIVE = 60
DEFAULT_QOS = 0

SERVICE_PUBLISH = 'publish'
EVENT_MQTT_MESSAGE_RECEIVED = 'MQTT_MESSAGE_RECEIVED'

DEPENDENCIES = []
REQUIREMENTS = ['paho-mqtt>=1.1']

CONF_BROKER = 'broker'
CONF_PORT = 'port'
CONF_TOPIC = 'topic'
CONF_KEEPALIVE = 'keepalive'
CONF_QOS = 'qos'

ATTR_QOS = 'qos'
ATTR_TOPIC = 'topic'
ATTR_SUBTOPIC = 'subtopic'
ATTR_PAYLOAD = 'payload'


def publish(hass, payload, subtopic=None):
    """ Send an MQTT message. """
    data = {ATTR_PAYLOAD: payload}
    if subtopic is not None:
        data[ATTR_SUBTOPIC] = subtopic
    hass.services.call(DOMAIN, SERVICE_PUBLISH, data)


def setup(hass, config):
    """ Get the MQTT protocol service. """

    if not validate_config(config, {DOMAIN: ['broker']}, _LOGGER):
        return False

    conf = config[DOMAIN]

    broker = conf[CONF_BROKER]
    port = util.convert(conf.get(CONF_PORT), int, DEFAULT_PORT)
    topic = util.convert(conf.get(CONF_TOPIC), str, DEFAULT_TOPIC)
    keepalive = util.convert(conf.get(CONF_KEEPALIVE), int, DEFAULT_KEEPALIVE)
    qos = util.convert(conf.get(CONF_QOS), int, DEFAULT_QOS)

    global MQTT_CLIENT
    try:
        MQTT_CLIENT = MQTT(hass, broker, port, keepalive, qos)
    except socket.error:
        _LOGGER.exception("Can't connect to the broker. "
                          "Please check your settings and the broker "
                          "itself.")
        return False

    def stop_mqtt(event):
        """ Stop MQTT component. """
        MQTT_CLIENT.stop()

    def start_mqtt(event):
        """ Launch MQTT component when Home Assistant starts up. """
        MQTT_CLIENT.subscribe('{}/#'.format(topic))
        MQTT_CLIENT.start()
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_mqtt)

    def publish_service(call):
        """ Handle MQTT publish service calls. """
        payload = call.data.get(ATTR_PAYLOAD)
        if payload is None:
            return
        subtopic = call.data.get(ATTR_SUBTOPIC)
        msg_topic = '{}/{}'.format(topic, subtopic) if subtopic else topic

        MQTT_CLIENT.publish(msg_topic, payload=payload)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_mqtt)

    hass.services.register(DOMAIN, SERVICE_PUBLISH, publish_service)

    return True


# This is based on one of the paho-mqtt examples:
# http://git.eclipse.org/c/paho/org.eclipse.paho.mqtt.python.git/tree/examples/sub-class.py
# pylint: disable=too-many-arguments, invalid-name
class MQTT(object):
    """ Implements messaging service for MQTT. """
    def __init__(self, hass, broker, port, keepalive, qos):
        import paho.mqtt.client as mqtt

        self.hass = hass
        self._qos = qos

        self._mqttc = mqtt.Client()
        self._mqttc.on_message = self.mqtt_on_message
        self._mqttc.connect(broker, port, keepalive)

    def mqtt_on_message(self, mqttc, obj, msg):
        """ Message callback """
        if '/' in msg.topic:
            msg_topic, msg_subtopic = msg.topic.split('/', 1)
        else:
            msg_topic, msg_subtopic = msg.topic, ''

        self.hass.bus.fire(EVENT_MQTT_MESSAGE_RECEIVED, {
            ATTR_TOPIC: msg_topic,
            ATTR_SUBTOPIC: msg_subtopic,
            ATTR_QOS: msg.qos,
            ATTR_PAYLOAD: msg.payload.decode('utf-8'),
        })

    def subscribe(self, topic):
        """ Subscribe to a topic. """
        self._mqttc.subscribe(topic, qos=self._qos)

    def unsubscribe(self, topic):
        """ Unsubscribe from topic. """
        self._mqttc.unsubscribe(topic)

    def stop(self):
        """ Stop the MQTT client. """
        self._mqttc.loop_stop()

    def start(self):
        """ Run the MQTT client. """
        self._mqttc.loop_start()

    def publish(self, topic, payload):
        """ Publish a MQTT message. """
        self._mqttc.publish(topic, payload)
