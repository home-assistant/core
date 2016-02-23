"""
Support for MQTT message handling..

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mqtt/
"""
import logging
import os
import socket
import time


from homeassistant.config import load_yaml_config_file
from homeassistant.exceptions import HomeAssistantError
import homeassistant.util as util
from homeassistant.helpers import template
from homeassistant.helpers import validate_config
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "mqtt"

MQTT_CLIENT = None

SERVICE_PUBLISH = 'publish'
EVENT_MQTT_MESSAGE_RECEIVED = 'mqtt_message_received'

REQUIREMENTS = ['paho-mqtt==1.1']

CONF_BROKER = 'broker'
CONF_PORT = 'port'
CONF_CLIENT_ID = 'client_id'
CONF_KEEPALIVE = 'keepalive'
CONF_USERNAME = 'username'
CONF_PASSWORD = 'password'
CONF_CERTIFICATE = 'certificate'
CONF_PROTOCOL = 'protocol'

PROTOCOL_31 = '3.1'
PROTOCOL_311 = '3.1.1'

DEFAULT_PORT = 1883
DEFAULT_KEEPALIVE = 60
DEFAULT_QOS = 0
DEFAULT_RETAIN = False
DEFAULT_PROTOCOL = PROTOCOL_311

ATTR_TOPIC = 'topic'
ATTR_PAYLOAD = 'payload'
ATTR_PAYLOAD_TEMPLATE = 'payload_template'
ATTR_QOS = 'qos'
ATTR_RETAIN = 'retain'

MAX_RECONNECT_WAIT = 300  # seconds


def _build_publish_data(topic, qos, retain):
    """Build the arguments for the publish service without the payload."""
    data = {ATTR_TOPIC: topic}
    if qos is not None:
        data[ATTR_QOS] = qos
    if retain is not None:
        data[ATTR_RETAIN] = retain
    return data


def publish(hass, topic, payload, qos=None, retain=None):
    """Publish message to an MQTT topic."""
    data = _build_publish_data(topic, qos, retain)
    data[ATTR_PAYLOAD] = payload
    hass.services.call(DOMAIN, SERVICE_PUBLISH, data)


def publish_template(hass, topic, payload_template, qos=None, retain=None):
    """Publish message to an MQTT topic using a template payload."""
    data = _build_publish_data(topic, qos, retain)
    data[ATTR_PAYLOAD_TEMPLATE] = payload_template
    hass.services.call(DOMAIN, SERVICE_PUBLISH, data)


def subscribe(hass, topic, callback, qos=DEFAULT_QOS):
    """Subscribe to an MQTT topic."""
    def mqtt_topic_subscriber(event):
        """Match subscribed MQTT topic."""
        if _match_topic(topic, event.data[ATTR_TOPIC]):
            callback(event.data[ATTR_TOPIC], event.data[ATTR_PAYLOAD],
                     event.data[ATTR_QOS])

    hass.bus.listen(EVENT_MQTT_MESSAGE_RECEIVED, mqtt_topic_subscriber)
    MQTT_CLIENT.subscribe(topic, qos)


def setup(hass, config):
    """Start the MQTT protocol service."""
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
    protocol = util.convert(conf.get(CONF_PROTOCOL), str, DEFAULT_PROTOCOL)

    if protocol not in (PROTOCOL_31, PROTOCOL_311):
        _LOGGER.error('Invalid protocol specified: %s. Allowed values: %s, %s',
                      protocol, PROTOCOL_31, PROTOCOL_311)
        return False

    # For cloudmqtt.com, secured connection, auto fill in certificate
    if certificate is None and 19999 < port < 30000 and \
       broker.endswith('.cloudmqtt.com'):
        certificate = os.path.join(os.path.dirname(__file__),
                                   'addtrustexternalcaroot.crt')

    global MQTT_CLIENT
    try:
        MQTT_CLIENT = MQTT(hass, broker, port, client_id, keepalive, username,
                           password, certificate, protocol)
    except socket.error:
        _LOGGER.exception("Can't connect to the broker. "
                          "Please check your settings and the broker "
                          "itself.")
        return False

    def stop_mqtt(event):
        """Stop MQTT component."""
        MQTT_CLIENT.stop()

    def start_mqtt(event):
        """Launch MQTT component when Home Assistant starts up."""
        MQTT_CLIENT.start()
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_mqtt)

    def publish_service(call):
        """Handle MQTT publish service calls."""
        msg_topic = call.data.get(ATTR_TOPIC)
        payload = call.data.get(ATTR_PAYLOAD)
        payload_template = call.data.get(ATTR_PAYLOAD_TEMPLATE)
        qos = call.data.get(ATTR_QOS, DEFAULT_QOS)
        retain = call.data.get(ATTR_RETAIN, DEFAULT_RETAIN)
        if payload is None:
            if payload_template is None:
                _LOGGER.error(
                    "You must set either '%s' or '%s' to use this service",
                    ATTR_PAYLOAD, ATTR_PAYLOAD_TEMPLATE)
                return
            try:
                payload = template.render(hass, payload_template)
            except template.jinja2.TemplateError as exc:
                _LOGGER.error(
                    "Unable to publish to '%s': rendering payload template of "
                    "'%s' failed because %s.",
                    msg_topic, payload_template, exc)
                return
        if msg_topic is None or payload is None:
            return
        MQTT_CLIENT.publish(msg_topic, payload, qos, retain)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_mqtt)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    hass.services.register(DOMAIN, SERVICE_PUBLISH, publish_service,
                           descriptions.get(SERVICE_PUBLISH))

    return True


# pylint: disable=too-many-arguments
class MQTT(object):
    """Home Assistant MQTT client."""

    def __init__(self, hass, broker, port, client_id, keepalive, username,
                 password, certificate, protocol):
        """Initialize Home Assistant MQTT client."""
        import paho.mqtt.client as mqtt

        self.hass = hass
        self.topics = {}
        self.progress = {}

        if protocol == PROTOCOL_31:
            proto = mqtt.MQTTv31
        else:
            proto = mqtt.MQTTv311

        if client_id is None:
            self._mqttc = mqtt.Client(protocol=proto)
        else:
            self._mqttc = mqtt.Client(client_id, protocol=proto)

        if username is not None:
            self._mqttc.username_pw_set(username, password)
        if certificate is not None:
            self._mqttc.tls_set(certificate)

        self._mqttc.on_subscribe = self._mqtt_on_subscribe
        self._mqttc.on_unsubscribe = self._mqtt_on_unsubscribe
        self._mqttc.on_connect = self._mqtt_on_connect
        self._mqttc.on_disconnect = self._mqtt_on_disconnect
        self._mqttc.on_message = self._mqtt_on_message

        self._mqttc.connect(broker, port, keepalive)

    def publish(self, topic, payload, qos, retain):
        """Publish a MQTT message."""
        self._mqttc.publish(topic, payload, qos, retain)

    def start(self):
        """Run the MQTT client."""
        self._mqttc.loop_start()

    def stop(self):
        """Stop the MQTT client."""
        self._mqttc.disconnect()
        self._mqttc.loop_stop()

    def subscribe(self, topic, qos):
        """Subscribe to a topic."""
        assert isinstance(topic, str)

        if topic in self.topics:
            return
        result, mid = self._mqttc.subscribe(topic, qos)
        _raise_on_error(result)
        self.progress[mid] = topic
        self.topics[topic] = None

    def unsubscribe(self, topic):
        """Unsubscribe from topic."""
        result, mid = self._mqttc.unsubscribe(topic)
        _raise_on_error(result)
        self.progress[mid] = topic

    def _mqtt_on_connect(self, _mqttc, _userdata, _flags, result_code):
        """On connect callback.

        Resubscribe to all topics we were subscribed to.
        """
        if result_code != 0:
            _LOGGER.error('Unable to connect to the MQTT broker: %s', {
                1: 'Incorrect protocol version',
                2: 'Invalid client identifier',
                3: 'Server unavailable',
                4: 'Bad username or password',
                5: 'Not authorised'
            }.get(result_code, 'Unknown reason'))
            self._mqttc.disconnect()
            return

        old_topics = self.topics

        self.topics = {key: value for key, value in self.topics.items()
                       if value is None}

        for topic, qos in old_topics.items():
            # qos is None if we were in process of subscribing
            if qos is not None:
                self.subscribe(topic, qos)

    def _mqtt_on_subscribe(self, _mqttc, _userdata, mid, granted_qos):
        """Subscribe successful callback."""
        topic = self.progress.pop(mid, None)
        if topic is None:
            return
        self.topics[topic] = granted_qos[0]

    def _mqtt_on_message(self, _mqttc, _userdata, msg):
        """Message received callback."""
        self.hass.bus.fire(EVENT_MQTT_MESSAGE_RECEIVED, {
            ATTR_TOPIC: msg.topic,
            ATTR_QOS: msg.qos,
            ATTR_PAYLOAD: msg.payload.decode('utf-8'),
        })

    def _mqtt_on_unsubscribe(self, _mqttc, _userdata, mid, granted_qos):
        """Unsubscribe successful callback."""
        topic = self.progress.pop(mid, None)
        if topic is None:
            return
        self.topics.pop(topic, None)

    def _mqtt_on_disconnect(self, _mqttc, _userdata, result_code):
        """Disconnected callback."""
        self.progress = {}
        self.topics = {key: value for key, value in self.topics.items()
                       if value is not None}

        # Remove None values from topic list
        for key in list(self.topics):
            if self.topics[key] is None:
                self.topics.pop(key)

        # When disconnected because of calling disconnect()
        if result_code == 0:
            return

        tries = 0
        wait_time = 0

        while True:
            try:
                if self._mqttc.reconnect() == 0:
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
    """Raise error if error result."""
    if result != 0:
        raise HomeAssistantError('Error talking to MQTT: {}'.format(result))


def _match_topic(subscription, topic):
    """Test if topic matches subscription."""
    if subscription.endswith('#'):
        return (subscription[:-2] == topic or
                topic.startswith(subscription[:-1]))

    sub_parts = subscription.split('/')
    topic_parts = topic.split('/')

    return (len(sub_parts) == len(topic_parts) and
            all(a == b for a, b in zip(sub_parts, topic_parts) if a != '+'))
