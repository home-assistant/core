"""
homeassistant.components.mqtt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
MQTT component, using paho-mqtt. This component needs a MQTT broker like
Mosquitto or Mosca. The Eclipse Foundation is running a public MQTT server
at iot.eclipse.org. If you prefer to use that one, keep in mind to adjust
the topic/client ID and that your messages are public.

Configuration:

To use MQTT you will need to add something like the following to your
config/configuration.yaml

mqtt:
  broker: 127.0.0.1
  port: 1883
  topic: home-assistant
  keepalive: 60
  client_id: home-assistant
  qos: 0
  retain: 0

For sending test messages:
$ mosquitto_pub -h 127.0.0.1 -t home-assistant/switch/1/on -m "Switch is ON"
For reading the messages:
$ mosquitto_sub -h 127.0.0.1 -v -t "home-assistant/#"
{"aaaaa":"1111"}
"""
import logging

from homeassistant.helpers.entity import Entity
from homeassistant.helpers import validate_config
from homeassistant.components.protocol import DOMAIN
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "mqtt"
DEPENDENCIES = []
MQTT_CLIENT = None
MQTT_SEND = 'mqtt_send'
EVENT_MQTT_MESSAGE_RECEIVED = 'MQTT_MESSAGE_RECEIVED'

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

    try:
        import paho.mqtt.client as mqtt

    except ImportError:
        _LOGGER.exception("Error while importing dependency paho-mqtt.")

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
                          "Please check your settings and the broker itself.")
            return False


        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_mqtt)

    def send_message(call):
        """ Sending an MQTT message. """
        subtopic = 'master'
        complete_topic = 'home-assistant/{}'.format(str(subtopic))
        MQTT_CLIENT.publish(complete_topic, str(call))


    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_mqtt)

    hass.services.register(DOMAIN, MQTT_SEND, send_message)
    hass.services.register(DOMAIN, EVENT_MQTT_MESSAGE_RECEIVED)


    return True


# This is based on one of the paho-mqtt examples:
# http://git.eclipse.org/c/paho/org.eclipse.paho.mqtt.python.git/tree/examples/sub-class.py
class MQTT(object):
    """ Implements messaging service for MQTT. """
    def __init__(self, hass, broker, port, topic, keepalive, clientid=None):

        import paho.mqtt.client as mqtt

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
        """ Subscribe callback"""
        complete_topic = self._topic + '/#'
        _LOGGER.info('Subscribed to %s', complete_topic)

    def mqtt_on_message(self, mqttc, obj, msg):
        """ Message callback """
        self.msg = '{} {} {}'.format(msg.topic, str(msg.qos), str(msg.payload))
        print(self.msg)
        self.hass.event.fire(EVENT_MQTT_MESSAGE_RECEIVED, {
            'topic': msg.topic,
            'subtopic': 'test',
            'qos': str(msg.qos),
            'payload': str(msg.payload),
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
