"""
homeassistant.components.mqtt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
MQTT component, using paho-mqtt.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mqtt/
"""
import logging
import os
import socket
import time


from homeassistant.exceptions import HomeAssistantError
import homeassistant.util as util
from homeassistant.helpers import validate_config
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "mqtt"

MQTT_CLIENT = None

DEFAULT_PORT = 1883
DEFAULT_KEEPALIVE = 60
DEFAULT_QOS = 0
DEFAULT_RETAIN = False

SERVICE_PUBLISH = 'publish'
EVENT_MQTT_MESSAGE_RECEIVED = 'MQTT_MESSAGE_RECEIVED'

REQUIREMENTS = ['paho-mqtt==1.1']

CONF_BROKER = 'broker'
CONF_PORT = 'port'
CONF_CLIENT_ID = 'client_id'
CONF_KEEPALIVE = 'keepalive'
CONF_USERNAME = 'username'
CONF_PASSWORD = 'password'
CONF_CERTIFICATE = 'certificate'

ATTR_TOPIC = 'topic'
ATTR_PAYLOAD = 'payload'
ATTR_QOS = 'qos'
ATTR_RETAIN = 'retain'

MAX_RECONNECT_WAIT = 300  # seconds


def publish(hass, topic, payload, qos=None, retain=None):
    """ Send an MQTT message. """
    data = {
        ATTR_TOPIC: topic,
        ATTR_PAYLOAD: payload,
    }
    if qos is not None:
        data[ATTR_QOS] = qos

    if retain is not None:
        data[ATTR_RETAIN] = retain

    hass.services.call(DOMAIN, SERVICE_PUBLISH, data)


def subscribe(hass, topic, callback, qos=DEFAULT_QOS):
    """ Subscribe to a topic. """
    def mqtt_topic_subscriber(event):
        """ Match subscribed MQTT topic. """
        if _match_topic(topic, event.data[ATTR_TOPIC]):
            callback(event.data[ATTR_TOPIC], event.data[ATTR_PAYLOAD],
                     event.data[ATTR_QOS])

    hass.bus.listen(EVENT_MQTT_MESSAGE_RECEIVED, mqtt_topic_subscriber)
    MQTT_CLIENT.subscribe(topic, qos)


def setup(hass, config):
    """ Get the MQTT protocol service. """

    if not validate_config(config, {DOMAIN: ['broker']}, _LOGGER):
        return False

    conf = config[DOMAIN]

    broker = conf[CONF_BROKER]
    port = util.convert(conf.get(CONF_PORT), int, DEFAULT_PORT)
    client_id = util.convert(conf.get(CONF_CLIENT_ID), str)
    keepalive = util.convert(conf.get(CONF_KEEPALIVE), int, DEFAULT_KEEPALIVE)
    username = util.convert(conf.get(CONF_USERNAME), str)
    password = util.convert(conf.get(CONF_PASSWORD), str)
    certificate = util.convert(conf.get(CONF_CERTIFICATE), str)

    # For cloudmqtt.com, secured connection, auto fill in certificate
    if certificate is None and 19999 < port < 30000 and \
       broker.endswith('.cloudmqtt.com'):
        certificate = os.path.join(os.path.dirname(__file__),
                                   'addtrustexternalcaroot.crt')

    global MQTT_CLIENT
    try:
        MQTT_CLIENT = MQTT(hass, broker, port, client_id, keepalive, username,
                           password, certificate)
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
        MQTT_CLIENT.start()
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_mqtt)

    def publish_service(call):
        """ Handle MQTT publish service calls. """
        msg_topic = call.data.get(ATTR_TOPIC)
        payload = call.data.get(ATTR_PAYLOAD)
        qos = call.data.get(ATTR_QOS, DEFAULT_QOS)
        retain = call.data.get(ATTR_RETAIN, DEFAULT_RETAIN)
        if msg_topic is None or payload is None:
            return
        MQTT_CLIENT.publish(msg_topic, payload, qos, retain)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_mqtt)

    hass.services.register(DOMAIN, SERVICE_PUBLISH, publish_service)

    return True


# pylint: disable=too-many-arguments
class MQTT(object):
    """ Implements messaging service for MQTT. """
    def __init__(self, hass, broker, port, client_id, keepalive, username,
                 password, certificate):
        import paho.mqtt.client as mqtt

        self.userdata = {
            'hass': hass,
            'topics': {},
            'progress': {},
        }

        if client_id is None:
            self._mqttc = mqtt.Client()
        else:
            self._mqttc = mqtt.Client(client_id)

        self._mqttc.user_data_set(self.userdata)

        if username is not None:
            self._mqttc.username_pw_set(username, password)
        if certificate is not None:
            self._mqttc.tls_set(certificate)

        self._mqttc.on_subscribe = _mqtt_on_subscribe
        self._mqttc.on_unsubscribe = _mqtt_on_unsubscribe
        self._mqttc.on_connect = _mqtt_on_connect
        self._mqttc.on_disconnect = _mqtt_on_disconnect
        self._mqttc.on_message = _mqtt_on_message

        self._mqttc.connect(broker, port, keepalive)

    def publish(self, topic, payload, qos, retain):
        """ Publish a MQTT message. """
        self._mqttc.publish(topic, payload, qos, retain)

    def start(self):
        """ Run the MQTT client. """
        self._mqttc.loop_start()

    def stop(self):
        """ Stop the MQTT client. """
        self._mqttc.loop_stop()

    def subscribe(self, topic, qos):
        """ Subscribe to a topic. """
        if topic in self.userdata['topics']:
            return
        result, mid = self._mqttc.subscribe(topic, qos)
        _raise_on_error(result)
        self.userdata['progress'][mid] = topic
        self.userdata['topics'][topic] = None

    def unsubscribe(self, topic):
        """ Unsubscribe from topic. """
        result, mid = self._mqttc.unsubscribe(topic)
        _raise_on_error(result)
        self.userdata['progress'][mid] = topic


def _mqtt_on_message(mqttc, userdata, msg):
    """ Message callback """
    userdata['hass'].bus.fire(EVENT_MQTT_MESSAGE_RECEIVED, {
        ATTR_TOPIC: msg.topic,
        ATTR_QOS: msg.qos,
        ATTR_PAYLOAD: msg.payload.decode('utf-8'),
    })


def _mqtt_on_connect(mqttc, userdata, flags, result_code):
    """ On connect, resubscribe to all topics we were subscribed to. """
    if result_code != 0:
        _LOGGER.error('Unable to connect to the MQTT broker: %s', {
            1: 'Incorrect protocol version',
            2: 'Invalid client identifier',
            3: 'Server unavailable',
            4: 'Bad username or password',
            5: 'Not authorised'
        }.get(result_code, 'Unknown reason'))
        mqttc.disconnect()
        return

    old_topics = userdata['topics']

    userdata['topics'] = {}
    userdata['progress'] = {}

    for topic, qos in old_topics.items():
        # qos is None if we were in process of subscribing
        if qos is not None:
            mqttc.subscribe(topic, qos)


def _mqtt_on_subscribe(mqttc, userdata, mid, granted_qos):
    """ Called when subscribe successful. """
    topic = userdata['progress'].pop(mid, None)
    if topic is None:
        return
    userdata['topics'][topic] = granted_qos


def _mqtt_on_unsubscribe(mqttc, userdata, mid, granted_qos):
    """ Called when subscribe successful. """
    topic = userdata['progress'].pop(mid, None)
    if topic is None:
        return
    userdata['topics'].pop(topic, None)


def _mqtt_on_disconnect(mqttc, userdata, result_code):
    """ Called when being disconnected. """
    # When disconnected because of calling disconnect()
    if result_code == 0:
        return

    tries = 0
    wait_time = 0

    while True:
        try:
            if mqttc.reconnect() == 0:
                _LOGGER.info('Successfully reconnected to the MQTT server')
                break
        except socket.error:
            pass

        wait_time = min(2**tries, MAX_RECONNECT_WAIT)
        _LOGGER.warning(
            'Disconnected from MQTT (%s). Trying to reconnect in %ss',
            result_code, wait_time)
        # It is ok to sleep here as we are in the MQTT thread.
        time.sleep(wait_time)
        tries += 1


def _raise_on_error(result):
    """ Raise error if error result. """
    if result != 0:
        raise HomeAssistantError('Error talking to MQTT: {}'.format(result))


def _match_topic(subscription, topic):
    """ Returns if topic matches subscription. """
    if subscription.endswith('#'):
        return (subscription[:-2] == topic or
                topic.startswith(subscription[:-1]))

    sub_parts = subscription.split('/')
    topic_parts = topic.split('/')

    return (len(sub_parts) == len(topic_parts) and
            all(a == b for a, b in zip(sub_parts, topic_parts) if a != '+'))
