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
  client_id: home-assistant
  qos: 0
  retain: 0

Variables:

broker
*Required
This is the IP address of your MQTT broker, e.g. 192.168.1.32.

port
*Required
The network port to connect to, e.g. 1883.

topic
*Required
The MQTT topic to subscribe to, e.g. home-assistant.

keepalive
*Required
The keep alive in seconds for this client, e.g. 60.

client_id
*Required
A name for this client, e.g. home-assistant.

qos: 0
*Required
Quality of service level to use for the subscription. 0, 1, or 2.

retain: 0
*Required
If message should be retained. 0 or 1.
"""
import logging

from homeassistant.helpers import validate_config
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

_LOGGER = logging.getLogger(__name__)

DOMAIN = "mqtt"
DEPENDENCIES = []
MQTT_CLIENT = None
MQTT_SEND = 'mqtt_send'
EVENT_MQTT_MESSAGE_RECEIVED = 'MQTT_MESSAGE_RECEIVED'
REQUIREMENTS = ['paho-mqtt>=1.1']


def setup(hass, config):
    """ Get the MQTT protocol service. """

    if not validate_config(config,
                           {DOMAIN: ['broker',
                                     'port',
                                     'topic',
                                     'keepalive',
                                     'client_id']},
                           _LOGGER):
        return False

    if mqtt is None:
        _LOGGER.error("Error while importing dependency 'paho-mqtt'.")
        return False

    global MQTT_CLIENT

    MQTT_CLIENT = MQTT(hass,
                       config[DOMAIN]['broker'],
                       config[DOMAIN]['port'],
                       config[DOMAIN]['topic'],
                       config[DOMAIN]['keepalive'],
                       config[DOMAIN]['client_id'])

    def stop_mqtt(event):
        """ Stop MQTT component. """
        MQTT_CLIENT.stop()

    def start_mqtt(event):
        """ Launch MQTT component when Home Assistant starts up. """
        try:
            MQTT_CLIENT.run()

        except ConnectionRefusedError:
            _LOGGER.exception("Can't connect to the broker. "
                              "Please check your settings and the broker"
                              "itself.")
            return False

        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_mqtt)

    def send_message(call):
        """ Sending an MQTT message. """
        subtopic = 'master'
        complete_topic = 'home-assistant/{}'.format(str(subtopic))
        MQTT_CLIENT.publish(complete_topic, str(call))

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_mqtt)

    hass.services.register(DOMAIN, MQTT_SEND, send_message)

    return True


# This is based on one of the paho-mqtt examples:
# http://git.eclipse.org/c/paho/org.eclipse.paho.mqtt.python.git/tree/examples/sub-class.py
# pylint: disable=too-many-arguments, invalid-name
class MQTT(object):
    """ Implements messaging service for MQTT. """
    def __init__(self, hass, broker, port, topic, keepalive, clientid=None):

        self.hass = hass
        self._broker = broker
        self._port = port
        self._topic = topic
        self._keepalive = keepalive
        self.msg = None

        self._mqttc = mqtt.Client(clientid)
        self._mqttc.on_message = self.mqtt_on_message
        self._mqttc.on_connect = self.mqtt_on_connect
        self._mqttc.on_publish = self.mqtt_on_publish
        self._mqttc.on_subscribe = self.mqtt_on_subscribe

    def mqtt_on_connect(self, mqttc, obj, flags, rc):
        """ Connect callback """
        _LOGGER.info('Connected to broker %s', self._broker)

    def mqtt_on_publish(self, mqttc, obj, mid):
        """ Publish callback """
        pass

    def mqtt_on_subscribe(self, mqttc, obj, mid, granted_qos):
        """ Subscribe callback """
        complete_topic = self._topic + '/#'
        _LOGGER.info('Subscribed to %s', complete_topic)

    def mqtt_on_message(self, mqttc, obj, msg):
        """ Message callback """
        self.hass.bus.fire(EVENT_MQTT_MESSAGE_RECEIVED, {
            'topic': msg.topic,
            'qos': str(msg.qos),
            'payload': msg.payload.decode('utf-8'),
        })

    def subscribe(self, topic):
        """ Subscribe to a topic. """
        self._mqttc.subscribe(self._topic, 0)

    def unsubscribe(self, topic):
        """ Unsubscribe from topic. """
        self._mqttc.unsubscribe(topic)

    def stop(self):
        """ Stop the MWTT client. """
        self._mqttc.loop_stop()

    def run(self):
        """ Run the MQTT client. """
        self._mqttc.connect(self._broker,
                            int(self._port),
                            int(self._keepalive))
        self._mqttc.subscribe(self._topic + '/#', 0)
        self._mqttc.loop_start()

    def publish(self, topic, payload):
        """ Publish a MQTT message. """
        self._mqttc.publish(topic, payload)
